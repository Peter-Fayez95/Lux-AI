"""
Input features for training imitation learning model

The start point is https://www.kaggle.com/shoheiazuma/lux-ai-with-imitation-learning
"""
import numpy as np

from lux.game_constants import GAME_CONSTANTS


IDENTIFIER_TO_OBJECT = {
    'u': 'unit',
    'ct': 'city_tile',
    'r': 'resource',
    'rp': 'research',
    'c': 'city',
    'ccd': 'road',
}


CHANNELS_MAP = dict(
    wood=0, coal=1, uranium=2,
    player_worker=3, player_cart=4, player_city=5,
    opponent_worker=6, opponent_cart=7, opponent_city=8,
    cooldown=9, road_level=10,
    player_city_fuel=11, opponent_city_fuel=12,
    player_unit_cargo=13, opponent_unit_cargo=14,
    player_unit_fuel=15, opponent_unit_fuel=16,
    player_city_can_survive_next_night=17, opponent_city_can_survive_next_night=18,
    player_city_can_survive_until_end=19, opponent_city_can_survive_until_end=20,
    resources_available=21, fuel_available=22,
    playable_area=23,
)


FEATURES_MAP = dict(
    step=0, is_night=1, is_last_day=2,
    player_research_points=3, opponent_research_points=4,
    is_player_in_coal_era=5, is_player_in_uranium_era=6,
    is_opponent_in_coal_era=7, is_opponent_in_uranium_era=8,
    player_n_cities=9, player_n_units=10,
    opponent_n_cities=11, opponent_n_units=12,
)


def make_input(obs):
    """
    Creates 3d board and 1d features that can be used as input to a model
    Values are normalized to avoid having quantities much bigger than one

    It also computes some dictionaries that could be later used to create the output for the model

    Returns
    -------
    board, features, active_units_to_position, active_cities_to_position, units_to_position
    """
    width, height = obs['width'], obs['height']
    city_id_to_survive_nights = {}

    board = np.zeros((len(CHANNELS_MAP), width, height), dtype=np.float32)
    features = np.zeros(len(FEATURES_MAP), dtype=np.float32)
    active_units_to_position = {}
    active_cities_to_position = {}
    units_to_position = {}

    for update in obs['updates']:
        splits = update.split(' ')
        input_identifier = splits[0]
        object_type = IDENTIFIER_TO_OBJECT.get(input_identifier, None)

        if object_type == 'unit':
            unit_type, team, unit_id, x, y, cooldown, wood, coal, uranium = parse_unit_info(splits)
            prefix = get_prefix_for_channels_map(team, obs)
            if is_worker(unit_type):
                board[CHANNELS_MAP['%s_worker' % prefix], x, y] += 1
            else:
                board[CHANNELS_MAP['%s_cart' % prefix], x, y] += 1
            board[CHANNELS_MAP['%s_unit_cargo' % prefix], x, y] = get_normalized_cargo(unit_type, wood, coal, uranium)
            board[CHANNELS_MAP['%s_unit_fuel' % prefix], x, y] = get_normalized_unit_fuel(unit_type, wood, coal, uranium)
            board[CHANNELS_MAP['cooldown'], x, y] = normalize_cooldown(cooldown)
            if prefix == 'player':
                units_to_position[unit_id] = (x, y)
                if cooldown < 1:
                    active_units_to_position[unit_id] = (x, y)
        elif object_type == 'city_tile':
            team, city_id, x, y, cooldown = parse_city_tile_info(splits)
            prefix = get_prefix_for_channels_map(team, obs)
            board[CHANNELS_MAP['%s_city' % prefix], x, y] = 1
            board[CHANNELS_MAP['%s_city_fuel' % prefix], x, y] = city_id_to_survive_nights[city_id]
            board[CHANNELS_MAP['%s_city_can_survive_next_night' % prefix], x, y] = \
                city_id_to_survive_nights[city_id] > (10 - max(obs['step'] % 40 - 30, 0))/10
            board[CHANNELS_MAP['%s_city_can_survive_until_end' % prefix], x, y] = \
                city_id_to_survive_nights[city_id] > (360 - obs['step'] ) // 40 + (10 - max(obs['step'] % 40 - 30, 0))/10
            board[CHANNELS_MAP['cooldown'], x, y] = normalize_cooldown(cooldown)
            if prefix == 'player' and cooldown < 1:
                active_cities_to_position['%s_%i' % (city_id, len(active_cities_to_position))] = (x, y)
        elif object_type == 'resource':
            resource_type, x, y, amount = parse_resource_info(splits)
            board[CHANNELS_MAP[resource_type], x, y] = amount / 800
        elif object_type == 'research':
            team, research_points = parse_research_points_info(splits)
            prefix = get_prefix_for_channels_map(team, obs)
            features[FEATURES_MAP['%s_research_points' % prefix]] = \
                research_points / GAME_CONSTANTS['PARAMETERS']['RESEARCH_REQUIREMENTS']['URANIUM']
            features[FEATURES_MAP['is_%s_in_coal_era' % prefix]] = \
                research_points >= GAME_CONSTANTS['PARAMETERS']['RESEARCH_REQUIREMENTS']['COAL']
            features[FEATURES_MAP['is_%s_in_uranium_era' % prefix]] = \
                research_points >= GAME_CONSTANTS['PARAMETERS']['RESEARCH_REQUIREMENTS']['URANIUM']
        elif object_type == 'city':
            team, city_id, fuel, lightupkeep = parse_city_info(splits)
            city_id_to_survive_nights[city_id] = fuel / lightupkeep / 10 # number of nights a city can survive (a night is 10 steps)
        elif object_type == 'road':
            x, y, road_level = parse_road_info(splits)
            board[CHANNELS_MAP['road_level'], x, y] = road_level/6

    board[CHANNELS_MAP['playable_area']] = 1
    add_resources_and_fuel_available_to_gather(board, features)

    features[FEATURES_MAP['step']] = obs['step'] / 360
    features[FEATURES_MAP['is_night']] = obs['step'] % 40 >= 30
    features[FEATURES_MAP['is_last_day']] = obs['step'] >= 40*8
    for prefix in ['player', 'opponent']:
        # Features are divided by 10 to avoid very big numbers
        features[FEATURES_MAP['%s_n_cities' % prefix]] = np.sum(board[CHANNELS_MAP['%s_city' % prefix]])/10
        features[FEATURES_MAP['%s_n_units' % prefix]] += np.sum(board[CHANNELS_MAP['%s_worker' % prefix]])/10
        features[FEATURES_MAP['%s_n_units' % prefix]] += np.sum(board[CHANNELS_MAP['%s_cart' % prefix]])/10

    board = np.transpose(board, axes=(1, 2, 0))
    features = np.expand_dims(features, axis=0)
    # TODO: add border to the board if necessary

    return board, features, active_units_to_position, active_cities_to_position, units_to_position


def parse_unit_info(splits):
    unit_type = int(splits[1])
    team = int(splits[2])
    unit_id = splits[3]
    x = int(splits[4])
    y = int(splits[5])
    cooldown = float(splits[6])
    wood = int(splits[7])
    coal = int(splits[8])
    uranium = int(splits[9])
    return unit_type, team, unit_id, x, y, cooldown, wood, coal, uranium


def parse_city_tile_info(splits):
    team = int(splits[1])
    city_id = splits[2]
    x = int(splits[3])
    y = int(splits[4])
    cooldown = float(splits[5])
    return team, city_id, x, y, cooldown


def parse_resource_info(splits):
    resource_type = splits[1]
    x = int(splits[2])
    y = int(splits[3])
    amount = int(float(splits[4]))
    return resource_type, x, y, amount


def parse_research_points_info(splits):
    team = int(splits[1])
    research_points = int(splits[2])
    return team, research_points


def parse_city_info(splits):
    team = int(splits[1])
    city_id = splits[2]
    fuel = float(splits[3])
    lightupkeep = float(splits[4])
    return team, city_id, fuel, lightupkeep


def parse_road_info(splits):
    x = int(splits[1])
    y = int(splits[2])
    road_level = float(splits[3])
    return x, y, road_level


def get_prefix_for_channels_map(team, obs):
    if team == obs['player']:
        prefix = 'player'
    else:
        prefix = 'opponent'
    return prefix


def is_worker(unit_type):
    return unit_type == 0


def get_normalized_cargo(unit_type, wood, coal, uranium):
    """
    Returns a value between 0 and 1 where 0 means the unit has no cargo, and 1 means that the unit
    is full
    """
    cargo = wood + coal + uranium
    if is_worker(unit_type):
        cargo /= GAME_CONSTANTS['PARAMETERS']['RESOURCE_CAPACITY']['WORKER']
    else:
        cargo /= GAME_CONSTANTS['PARAMETERS']['RESOURCE_CAPACITY']['CART']
    return cargo


def get_normalized_unit_fuel(unit_type, wood, coal, uranium):
    """
    Returns a value between 0 and 1 where 0 means the unit has no fuel, and 1 means that the unit
    is full with uranium
    """
    fuel_rate = GAME_CONSTANTS['PARAMETERS']['RESOURCE_TO_FUEL_RATE']
    resource_capacity = GAME_CONSTANTS['PARAMETERS']['RESOURCE_CAPACITY']

    fuel = wood*fuel_rate['WOOD'] \
        + coal*fuel_rate['COAL'] \
        + uranium*fuel_rate['URANIUM']
    if is_worker(unit_type):
        fuel /= resource_capacity['WORKER']
    else:
        fuel /= resource_capacity['CART']
    fuel /= fuel_rate['URANIUM']
    return fuel


def normalize_cooldown(cooldown):
    return (cooldown - 1)/10


def add_resources_and_fuel_available_to_gather(board, features):
    collection_rate = GAME_CONSTANTS['PARAMETERS']['WORKER_COLLECTION_RATE']
    fuel_rate = GAME_CONSTANTS['PARAMETERS']['RESOURCE_TO_FUEL_RATE']

    board[CHANNELS_MAP['resources_available']] += (board[CHANNELS_MAP['wood']] > 0)*collection_rate['WOOD']
    if features[FEATURES_MAP['is_player_in_coal_era']]:
        board[CHANNELS_MAP['resources_available']] += (board[CHANNELS_MAP['coal']] > 0)*collection_rate['COAL']
    if features[FEATURES_MAP['is_player_in_uranium_era']]:
        board[CHANNELS_MAP['resources_available']] += (board[CHANNELS_MAP['uranium']] > 0)*collection_rate['URANIUM']
    _expand_available_resource(board[CHANNELS_MAP['resources_available']])
    board[CHANNELS_MAP['resources_available']] /= collection_rate['WOOD']*5

    board[CHANNELS_MAP['fuel_available']] += (board[CHANNELS_MAP['wood']] > 0)*collection_rate['WOOD']*fuel_rate['WOOD']
    if features[FEATURES_MAP['is_player_in_coal_era']]:
        board[CHANNELS_MAP['fuel_available']] += (board[CHANNELS_MAP['coal']] > 0)*collection_rate['COAL']*fuel_rate['COAL']
    if features[FEATURES_MAP['is_player_in_uranium_era']]:
        board[CHANNELS_MAP['fuel_available']] += (board[CHANNELS_MAP['uranium']] > 0)*collection_rate['URANIUM']*fuel_rate['URANIUM']
    _expand_available_resource(board[CHANNELS_MAP['fuel_available']])
    board[CHANNELS_MAP['fuel_available']] /= collection_rate['URANIUM']*fuel_rate['URANIUM']*5


def _expand_available_resource(channel):
    channel_original = channel.copy()
    channel[:-1] += channel_original[1:]
    channel[1:] += channel_original[:-1]
    channel[:, :-1] += channel_original[:, 1:]
    channel[:, 1:] += channel_original[:, :-1]


def expand_board_size_adding_zeros(board, size=32):
    """
    Increases the board size by default to 32x32 by adding zeros. The input should be a 4d array
    """
    board_size = board.shape[1]
    if board_size < size:
        expanded_board = np.zeros((board.shape[0], size, size, board.shape[3]), dtype=board.dtype)
        offset = (size - board_size)//2
        expanded_board[:, offset:-offset, offset:-offset] = board
        return expanded_board
    elif board_size == size:
        return board
    else:
        raise NotImplementedError()


def crop_board_to_original_size(board, observation):
    """
    Increases the board size by default to 32x32 by adding zeros. The input should be a 4d array
    """
    original_size = observation['width']
    board_size = board.shape[1]
    if board_size > original_size:
        offset = (board_size - original_size)//2
        return board[:, offset:-offset, offset:-offset]
    elif board_size == original_size:
        return board
    else:
        raise NotImplementedError()


"""
Output features for imitation learning
"""
import warnings
import numpy as np


def create_actions_mask(active_units_to_position, observation):
    width, height = observation['width'], observation['height']
    mask = np.zeros((width, height, 1), dtype=np.float32)
    for position in active_units_to_position.values():
        x, y = position
        mask[x, y] = 1
    return mask


UNIT_ACTIONS_MAP = {
    'm n': 0, # move north
    'm e': 1, # move east
    'm s': 2, # move south
    'm w': 3, # move west
    't n': 4, # transfer north
    't e': 5, # transfer east
    't s': 6, # transfer south
    't w': 7, # transfer west
    'bcity': 8, # build city
    'p': 9, # pillage
}


CITY_ACTIONS_MAP = {
    'r': 0, # research
    'bw': 1, # build worker
    'bc': 2, # build cart
}


def create_output_features(actions, units_to_position, observation):
    width, height = observation['width'], observation['height']

    unit_actions = np.zeros((len(UNIT_ACTIONS_MAP), width, height), dtype=np.float32)
    city_actions = np.zeros((len(CITY_ACTIONS_MAP), width, height), dtype=np.float32)
    for action in actions:
        splits = action.split(' ')
        action_id = splits[0]
        if action_id in CITY_ACTIONS_MAP:
            x, y = int(splits[1]), int(splits[2])
            city_actions[CITY_ACTIONS_MAP[action_id], x, y] = 1
        elif action_id == 'm': # move
            unit_id, direction = splits[1], splits[2]
            x, y = units_to_position[unit_id]
            if direction == 'c':
                continue
            unit_actions[UNIT_ACTIONS_MAP['%s %s' % (action_id, direction)], x, y] = 1
        elif action_id == 't': # transfer
            unit_id, dst_id = splits[1], splits[2]
            try:
                x, y = units_to_position[unit_id]
                x_dst, y_dst = units_to_position[dst_id]
                direction = get_transfer_direction(x, y, x_dst, y_dst)
                unit_actions[UNIT_ACTIONS_MAP['%s %s' % (action_id, direction)], x, y] = 1
            except KeyError:
                # I have found that for 26458198.json player 0 there is an incorrect transfer action
                warnings.warn('Could not create transfer action because there were missing units')
        elif action_id in {'bcity', 'p'}:
            unit_id = splits[1]
            x, y = units_to_position[unit_id]
            unit_actions[UNIT_ACTIONS_MAP[action_id], x, y] = 1
    # to channels last convention
    unit_actions = np.transpose(unit_actions, axes=(1, 2, 0))
    city_actions = np.transpose(city_actions, axes=(1, 2, 0))
    return unit_actions, city_actions


def get_transfer_direction(x_source, y_source, x_dst, y_dst):
    if x_dst < x_source:
        return 'w'
    elif x_dst > x_source:
        return 'e'
    elif y_dst < y_source:
        return 'n'
    elif y_dst > y_source:
        return 's'
    else:
        raise Exception('Could not compute transfer direction for: %s' % str((x_source, y_source, x_dst, y_dst)))


"""
Functions for generating actions from model predictions
"""
import numpy as np

#from luxai.input_features import parse_unit_info
#from luxai.output_features import CITY_ACTIONS_MAP, UNIT_ACTIONS_MAP


def create_actions_for_cities_from_model_predictions(preds, active_cities_to_position, action_threshold=0.5):
    """
    Creates actions in the luxai format from the predictions of the model

    Parameters
    ----------
    preds : 3d array
        3d array with the predictions being the dimensions (x, y, action)
    active_cities_to_position : dict
        A dictionary that maps city tile identifier to x, y position
    action_threshold : float
        A threshold that filters predictions with a smaller value than that
    """
    actions = []
    idx_to_action = {idx: name for name, idx in CITY_ACTIONS_MAP.items()}
    for position in active_cities_to_position.values():
        x, y = position
        city_preds = preds[x, y]
        action_idx = np.argmax(city_preds)
        if city_preds[action_idx] > action_threshold:
            action_key = idx_to_action[action_idx]
            actions.append('%s %i %i' % (action_key, x, y))
    return actions


def create_actions_for_units_from_model_predictions(
        preds, active_units_to_position, units_to_position, observation, action_threshold=0.5):
    """
    Creates actions in the luxai format from the predictions of the model

    Parameters
    ----------
    preds : 3d array
        3d array with the predictions being the dimensions (x, y, action)
    active_units_to_position : dict
        A dictionary that maps active unit identifier to x,y position
    units_to_position : dict
        A dictionary that maps all unit identifier to x,y position
    action_threshold : float
        A threshold that filters predictions with a smaller value than that
    """
    preds = preds.copy()
    actions = []
    idx_to_action = {idx: name for name, idx in UNIT_ACTIONS_MAP.items()}
    for unit_id, position in active_units_to_position.items():
        x, y = position
        unit_preds = preds[x, y]
        action_idx = np.argmax(unit_preds)
        if unit_preds[action_idx] > action_threshold:
            action_key = idx_to_action[action_idx]
            actions.append(create_unit_action(action_key, unit_id, units_to_position, observation))
            # This ensures that units with overlap do not repeat actions
            preds[x, y, action_idx] = 0
    # TODO: deal with collisions
    return actions


def create_unit_action(action_key, unit_id, units_to_position, observation):
    action_id = action_key.split(' ')[0]
    if action_id == 'm':
        action = 'm %s %s' % (unit_id, action_key.split(' ')[-1])
        return action
    elif action_id in ['bcity', 'p']:
        action = '%s %s' % (action_id, unit_id)
        return action
    elif action_id == 't':
        direction = action_key.split(' ')[1]
        position = units_to_position[unit_id]
        dst_position = _get_dst_position(position, direction)
        dst_unit_id = _find_unit_in_position(dst_position, units_to_position)
        resource, amount = _get_most_abundant_resource_from_unit(unit_id, observation)
        return 't %s %s %s %i' % (unit_id, dst_unit_id, resource, amount)
    else:
        raise KeyError(action_id)


def _get_dst_position(position, direction):
    if direction == 'n':
        dst_position = (position[0], position[1] - 1)
    elif direction == 'e':
        dst_position = (position[0] + 1, position[1])
    elif direction == 's':
        dst_position = (position[0], position[1] + 1)
    elif direction == 'w':
        dst_position = (position[0] - 1, position[1])
    return dst_position


def _find_unit_in_position(position, units_to_position):
    for other_unit_id, other_position in units_to_position.items():
        if other_position == position:
            return other_unit_id


def _get_most_abundant_resource_from_unit(unit_id, observation):
    key = ' %s ' % unit_id
    for update in observation['updates']:
        if key in update:
            resources = parse_unit_info(update.split(' '))[-3:]
            resource_names = ['wood', 'coal', 'uranium']
            idx = np.argmax(resources)
            return resource_names[idx], resources[idx]
    raise KeyError(unit_id)



"""
Agent code for cunet model
"""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import tensorflow as tf
import numpy as np
import cunet.train.models.FiLM_utils

try:
    SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
    model_path = os.path.join(SCRIPT_DIR, 'model.h5')
except NameError:
    # this happens when using python for playing matches
    # original model path: /mnt/hdd0/Kaggle/luxai/models/10_repeat_with_python_37/01_filters32_depth4_condition_16_complex/best_val_loss_model.h5
    model_path = '/mnt/hdd0/MEGA/AI/22 Kaggle/luxai/agents/clown/model.h5'
model = tf.keras.models.load_model(model_path, compile=False)


def agent(observation, configuration):
    ret = make_input(observation)
    board, features = ret[:2]
    preds = model.predict([
        expand_board_size_adding_zeros(np.expand_dims(board, axis=0)),
        np.expand_dims(features, axis=0)])
    preds = [crop_board_to_original_size(pred, observation) for pred in preds]
    active_units_to_position, active_cities_to_position, units_to_position = ret[2:]
    actions = create_actions_for_units_from_model_predictions(
        preds[0][0], active_units_to_position, units_to_position, observation)
    actions += create_actions_for_cities_from_model_predictions(preds[1][0], active_cities_to_position)
    return actions



