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
    player_is_unit_full=23, is_cell_emtpy=24, player_can_build_city=25,
    player_obstacles=26, playable_area=27,
)


FEATURES_MAP = dict(
    step=0, is_night=1, is_last_day=2,
    player_research_points=3, opponent_research_points=4,
    is_player_in_coal_era=5, is_player_in_uranium_era=6,
    is_opponent_in_coal_era=7, is_opponent_in_uranium_era=8,
    # player_n_cities=9, player_n_units=10,
    # opponent_n_cities=11, opponent_n_units=12,
    # hour=13, city_diff=14,
    # unit_free_slots=15,
    hour=9, city_diff=10,
    unit_free_slots=11,
)


def make_input(obs):
    """
    Creates 3d board and 1d features that can be used as input to a model
    Values are normalized to avoid having quantities much bigger than one

    It also computes some dictionaries that could be later used to create the output for the model

    Returns
    -------
    board, features, active_unit_to_position, active_city_to_position, unit_to_position
    """
    width, height = obs['width'], obs['height']
    city_id_to_survive_nights = {}

    board = np.zeros((len(CHANNELS_MAP), width, height), dtype=np.float32)
    features = np.zeros(len(FEATURES_MAP), dtype=np.float32)
    active_unit_to_position, active_city_to_position = dict(), dict()
    unit_to_position, city_to_position = dict(), dict()

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
                unit_to_position[unit_id] = (x, y)
                if cooldown < 1:
                    active_unit_to_position[unit_id] = (x, y)
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
            if prefix == 'player':
                city_to_position['%s_%i' % (city_id, len(city_to_position))] = (x, y)
                if cooldown < 1:
                    active_city_to_position['%s_%i' % (city_id, len(active_city_to_position))] = (x, y)
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
    board[CHANNELS_MAP['player_is_unit_full']] = board[CHANNELS_MAP['player_unit_cargo']] == 1
    board[CHANNELS_MAP['is_cell_emtpy']] = _is_cell_empty(board)
    board[CHANNELS_MAP['player_can_build_city']] = _player_can_build_city(board)
    board[CHANNELS_MAP['player_obstacles']] = _player_obstacles(board)
    add_resources_and_fuel_available_to_gather(board, features)

    features[FEATURES_MAP['step']] = obs['step'] / 360
    features[FEATURES_MAP['is_night']] = obs['step'] % 40 >= 30
    features[FEATURES_MAP['is_last_day']] = obs['step'] >= 40*8
    features[FEATURES_MAP['hour']] = obs['step'] % 40 / 40
    features[FEATURES_MAP['city_diff']] = np.sum(board[CHANNELS_MAP['player_city']]) - np.sum(board[CHANNELS_MAP['opponent_city']])
    features[FEATURES_MAP['unit_free_slots']] = np.sum(board[CHANNELS_MAP['player_city']]) - np.sum(board[CHANNELS_MAP['player_worker']]) - np.sum(board[CHANNELS_MAP['player_cart']])
    # for prefix in ['player', 'opponent']:
    #     # Features are divided by 10 to avoid very big numbers
    #     features[FEATURES_MAP['%s_n_cities' % prefix]] = np.sum(board[CHANNELS_MAP['%s_city' % prefix]])/10
    #     features[FEATURES_MAP['%s_n_units' % prefix]] += np.sum(board[CHANNELS_MAP['%s_worker' % prefix]])/10
    #     features[FEATURES_MAP['%s_n_units' % prefix]] += np.sum(board[CHANNELS_MAP['%s_cart' % prefix]])/10

    board = np.transpose(board, axes=(1, 2, 0))
    features = np.expand_dims(features, axis=0)

    return board, features, active_unit_to_position, active_city_to_position, unit_to_position, city_to_position


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


def _is_cell_empty(board):
    is_cell_used = board[CHANNELS_MAP['player_city']] + board[CHANNELS_MAP['opponent_city']]
    is_cell_used += board[CHANNELS_MAP['wood']] + board[CHANNELS_MAP['coal']] + board[CHANNELS_MAP['uranium']]
    return is_cell_used == 0


def _player_can_build_city(board):
    can_build_city = board[CHANNELS_MAP['player_is_unit_full']].copy()
    can_build_city *= board[CHANNELS_MAP['is_cell_emtpy']]
    can_build_city *= np.clip(board[CHANNELS_MAP['player_worker']], None, 1)
    can_build_city *= (board[CHANNELS_MAP['cooldown']] < 0)
    return can_build_city


def _player_obstacles(board):
    obstacles = board[CHANNELS_MAP['opponent_city']]
    frozen_units = board[CHANNELS_MAP['cooldown']] >= 0
    for key in ['player', 'opponent']:
        units = board[CHANNELS_MAP['%s_worker' % key]] + board[CHANNELS_MAP['%s_cart' % key]]
        obstacles += (1 - board[CHANNELS_MAP['%s_city' % key]])*units*frozen_units
    return obstacles


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


def create_actions_mask(active_unit_to_position, observation):
    width, height = observation['width'], observation['height']
    mask = np.zeros((width, height, 1), dtype=np.float32)
    for position in active_unit_to_position.values():
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


def create_output_features(actions, unit_to_position, observation):
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
            x, y = unit_to_position[unit_id]
            if direction == 'c':
                continue
            unit_actions[UNIT_ACTIONS_MAP['%s %s' % (action_id, direction)], x, y] = 1
        elif action_id == 't': # transfer
            unit_id, dst_id = splits[1], splits[2]
            try:
                x, y = unit_to_position[unit_id]
                x_dst, y_dst = unit_to_position[dst_id]
                direction = get_transfer_direction(x, y, x_dst, y_dst)
                unit_actions[UNIT_ACTIONS_MAP['%s %s' % (action_id, direction)], x, y] = 1
            except KeyError:
                # I have found that for 26458198.json player 0 there is an incorrect transfer action
                warnings.warn('Could not create transfer action because there were missing units')
            except SamePositionException:
                warnings.warn('Could not create transfer action because source and dst unit are at the same place')
        elif action_id in {'bcity', 'p'}:
            unit_id = splits[1]
            x, y = unit_to_position[unit_id]
            unit_actions[UNIT_ACTIONS_MAP[action_id], x, y] = 1
    # to channels last convention
    unit_actions = np.transpose(unit_actions, axes=(1, 2, 0))
    city_actions = np.transpose(city_actions, axes=(1, 2, 0))
    return unit_actions, city_actions

class SamePositionException(Exception):
    pass

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
        raise SamePositionException('Could not compute transfer direction for: %s' % str((x_source, y_source, x_dst, y_dst)))


"""
Functions for generating actions from model predictions
"""
import numpy as np
import random

from lux.game_constants import GAME_CONSTANTS

#from luxai.input_features import parse_unit_info
#from luxai.output_features import CITY_ACTIONS_MAP, UNIT_ACTIONS_MAP


def create_actions_for_cities_from_model_predictions(preds, active_city_to_position,
                                                     empty_unit_slots, action_threshold=0.5,
                                                     is_post_processing_enabled=True,
                                                     policy='greedy'):
    """
    Creates actions in the luxai format from the predictions of the model

    Parameters
    ----------
    preds : 3d array
        3d array with the predictions being the dimensions (x, y, action)
    active_city_to_position : dict
        A dictionary that maps city tile identifier to x, y position
    action_threshold : float
        A threshold that filters predictions with a smaller value than that
    empty_unit_slots : int
        Number of units that can be build
    is_post_processing_enabled: bool
        If true it won't build units if there are not empty_unit_slots
    policy : str
        Name of the policy we want to use to choose action, f.e. greedy
    """
    preds = preds.copy()
    actions = []
    idx_to_action = {idx: name for name, idx in CITY_ACTIONS_MAP.items()}
    city_to_priority = {city_id: np.max(preds[x, y]) for city_id, (x, y) in active_city_to_position.items()}
    for city_id in rank_units_based_on_priority(city_to_priority):
        x, y = active_city_to_position[city_id]
        city_preds = preds[x, y]
        if empty_unit_slots <= 0 and is_post_processing_enabled:
            city_preds[CITY_ACTIONS_MAP['bw']] = 0
            city_preds[CITY_ACTIONS_MAP['bc']] = 0
        action_idx = choose_action_idx_from_predictions(city_preds, policy, action_threshold)
        if action_idx is not None:
            action_key = idx_to_action[action_idx]
            actions.append('%s %i %i' % (action_key, x, y))
            if action_key in ['bw', 'bc']:
                empty_unit_slots -= 1
    return actions


def choose_action_idx_from_predictions(preds, policy, action_threshold):
    if policy == 'greedy':
        action_idx = np.argmax(preds)
        if preds[action_idx] <= action_threshold:
            action_idx = None
    elif policy == 'random':
        candidate_indices = [idx for idx, pred in enumerate(preds) if pred > action_threshold]
        if candidate_indices:
            action_idx = random.choices(candidate_indices,
                                        weights=[preds[idx] for idx in candidate_indices])[0]
        else:
            action_idx = None
    return action_idx


def create_actions_for_units_from_model_predictions(
        preds, active_unit_to_position, unit_to_position, observation, city_positions,
        action_threshold=0.5, is_post_processing_enabled=True, policy='greedy'):
    """
    Creates actions in the luxai format from the predictions of the model

    Parameters
    ----------
    preds : 3d array
        3d array with the predictions being the dimensions (x, y, action)
    active_unit_to_position : dict
        A dictionary that maps active unit identifier to x,y position
    unit_to_position : dict
        A dictionary that maps all unit identifier to x,y position
    observation : dict
        Dictionary with the observation of the game
    city_positions : set or list
        A set with all the positions of the cities
    action_threshold : float
        A threshold that filters predictions with a smaller value than that
    is_post_processing_enabled: bool
        If true actions with collisions will be removed and cities won't be built if not enough
        resources are available
    """
    preds = preds.copy()
    if is_post_processing_enabled:
        preds = apply_can_city_be_built_mask_to_preds(preds, active_unit_to_position, observation)
    idx_to_action = {idx: name for name, idx in UNIT_ACTIONS_MAP.items()}
    unit_to_action, unit_to_priority = {}, {}
    for unit_id, position in active_unit_to_position.items():
        x, y = position
        unit_preds = preds[x, y]
        action_idx = choose_action_idx_from_predictions(unit_preds, policy, action_threshold)
        if action_idx is not None:
            action_key = idx_to_action[action_idx]
            unit_to_action[unit_id] = create_unit_action(action_key, unit_id, unit_to_position, observation)
            unit_to_priority[unit_id] = unit_preds[action_idx]
            # This ensures that units with overlap do not repeat actions
            preds[x, y, action_idx] = 0
    if is_post_processing_enabled:
        remove_collision_actions(unit_to_action, unit_to_position, unit_to_priority, city_positions)
    return list(unit_to_action.values())


def create_unit_action(action_key, unit_id, unit_to_position, observation):
    action_id = action_key.split(' ')[0]
    if action_id == 'm':
        action = 'm %s %s' % (unit_id, action_key.split(' ')[-1])
        return action
    elif action_id in ['bcity', 'p']:
        action = '%s %s' % (action_id, unit_id)
        return action
    elif action_id == 't':
        direction = action_key.split(' ')[1]
        position = unit_to_position[unit_id]
        dst_position = _get_dst_position(position, direction)
        dst_unit_id = _find_unit_in_position(dst_position, unit_to_position)
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
    elif direction == 'c':
        dst_position = position
    else:
        raise KeyError(direction)
    return dst_position


def _find_unit_in_position(position, unit_to_position):
    for other_unit_id, other_position in unit_to_position.items():
        if other_position == position:
            return other_unit_id


def _get_most_abundant_resource_from_unit(unit_id, observation):
    resources = _get_unit_resources(unit_id, observation)
    resource_names = ['wood', 'coal', 'uranium']
    idx = np.argmax(resources)
    return resource_names[idx], resources[idx]


def _get_unit_resources(unit_id, observation):
    key = ' %s ' % unit_id
    for update in observation['updates']:
        if key in update:
            resources = parse_unit_info(update.split(' '))[-3:]
            return resources
    raise KeyError(unit_id)


def remove_collision_actions(unit_to_action, unit_to_position, unit_to_priority, city_positions):
    blocked_positions = get_blocked_positions_using_units_that_do_not_move(
        unit_to_position, unit_to_action, city_positions)
    for unit_id in rank_units_based_on_priority(unit_to_priority):
        action = unit_to_action[unit_id]
        if action.startswith('m '):
            direction = action.split(' ')[-1]
            position = unit_to_position[unit_id]
            next_position = _get_dst_position(position, direction)
            if next_position in blocked_positions:
                unit_to_action.pop(unit_id)
            elif next_position not in city_positions:
                blocked_positions.add(next_position)


def get_blocked_positions_using_units_that_do_not_move(unit_to_position, unit_to_action, city_positions):
    """
    Returns a set of positions of units that do not move and are outside a city
    """
    blocked_positions = set()
    for unit_id, position in unit_to_position.items():
        if unit_id in unit_to_action:
            action = unit_to_action[unit_id]
            if not action.startswith('m ') and position not in city_positions:
                blocked_positions.add(position)
        else:
            if position not in city_positions:
                blocked_positions.add(position)
    return blocked_positions


def rank_units_based_on_priority(unit_to_priority):
    units = np.array(list(unit_to_priority.keys()))
    priority = [unit_to_priority[unit_id] for unit_id in units]
    return units[np.argsort(priority)[::-1]].tolist()


def apply_can_city_be_built_mask_to_preds(preds, active_unit_to_position, observation):
    mask = np.zeros(preds.shape[:-1])
    for unit_id, position in active_unit_to_position.items():
        x, y = position
        resources = _get_unit_resources(unit_id, observation)
        if sum(resources) >= GAME_CONSTANTS['PARAMETERS']['CITY_BUILD_COST']:
            mask[x, y] = 1
    preds[:, :, UNIT_ACTIONS_MAP['bcity']] *= mask
    return preds



"""
Data augmentation
"""
import random
from functools import lru_cache
import numpy as np

#from luxai.output_features import UNIT_ACTIONS_MAP


def random_data_augmentation(x, y):
    """
    Applies random data augmentation to the given batch
    """
    if random.randint(0, 1):
        x, y = horizontal_flip(x, y)
    n_rotations = random.randint(0, 3)
    if n_rotations:
        x, y = rotation_90(x, y, n_rotations)
    return x, y


def horizontal_flip(x, y):
    """
    Horizontal flip on training data
    x is expected to have size (batch_size, 32, 32, 24), (batch_size, 1, 13)
    y is expected to have size (batch_size, 32, 32, unit_actions + 1 ), (batch_size, 32, 32, city_actions + 1)

    I will simply flip the first axis and rearrange the unit action channels. First axis is x, so
    actions involved are east and west
    """
    return horizontal_flip_input(x), horizontal_flip_output(y)


def horizontal_flip_input(x):
    x = (x[0][:, ::-1], x[1])
    return x


def horizontal_flip_output(y):
    if len(y) == 4:
        unit_actions_indices = _get_horizontal_flip_unit_actions_indices()[:y[1].shape[-1]]
        y = (y[0][:, ::-1], y[1][:, ::-1, :, unit_actions_indices], y[2][:, ::-1], y[3][:, ::-1])
    elif len(y) == 2:
        unit_actions_indices = _get_horizontal_flip_unit_actions_indices()[:y[0].shape[-1]]
        y = (y[0][:, ::-1, :, unit_actions_indices], y[1][:, ::-1])
    else:
        raise NotImplementedError(len(y))
    return y


@lru_cache(maxsize=1)
def _get_horizontal_flip_unit_actions_indices():
    idx_to_action = {value: key for key, value in UNIT_ACTIONS_MAP.items()}
    def apply_horizontal_flip_to_action(action):
        if action.endswith('e'):
            return action.replace('e', 'w')
        elif action.endswith('w'):
            return action.replace('w', 'e')
        else:
            return action
    indices = [UNIT_ACTIONS_MAP[apply_horizontal_flip_to_action(idx_to_action[idx])] \
        for idx in range(len(UNIT_ACTIONS_MAP))]
    indices.append(len(UNIT_ACTIONS_MAP))
    return indices


def rotation_90(x, y, n_times):
    return rotation_90_input(x, n_times), rotation_90_output(y, n_times)


def rotation_90_input(x, n_times):
    x = (np.rot90(x[0], axes=(1, 2), k=n_times), x[1])
    return x


def rotation_90_output(y, n_times):
    if len(y) == 4:
        unit_actions_indices = _get_rotation_unit_actions_indices(n_times)[:y[1].shape[-1]]
        y = (np.rot90(y[0], axes=(1, 2), k=n_times),
             np.rot90(y[1], axes=(1, 2), k=n_times)[:, :, :, unit_actions_indices],
             np.rot90(y[2], axes=(1, 2), k=n_times),
             np.rot90(y[3], axes=(1, 2), k=n_times))
    elif len(y) == 2:
        unit_actions_indices = _get_rotation_unit_actions_indices(n_times)[:y[0].shape[-1]]
        y = (np.rot90(y[0], axes=(1, 2), k=n_times)[:, :, :, unit_actions_indices],
             np.rot90(y[1], axes=(1, 2), k=n_times))
    else:
        raise NotImplementedError(len(y))
    return y


@lru_cache(maxsize=4)
def _get_rotation_unit_actions_indices(n_times):
    indices = (np.arange(4) - n_times) % 4
    indices = indices.tolist() + (indices + 4).tolist() + list(range(8, 11))
    return indices



"""
Agent code for cunet model
"""
import os
import glob
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import tensorflow as tf
import numpy as np
import cunet.train.models.FiLM_utils

# original model paths: ['/mnt/hdd0/Kaggle/luxai/models/51_models_for_submissions/seed0_threshold1700_512x4_oversample2/best_val_loss_model.h5']
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
model_paths = sorted(glob.glob(os.path.join(SCRIPT_DIR, '*.h5')))
models = [tf.keras.models.load_model(model_path, compile=False) for model_path in model_paths]


def predict_with_data_augmentation(model, model_input):
    preds = []
    for apply_horizontal_flip in range(2):
        for n_rotations in range(1):
            augmented_model_input = [x.copy() for x in model_input]
            if apply_horizontal_flip:
                augmented_model_input = list(horizontal_flip_input(augmented_model_input))
            if n_rotations:
                augmented_model_input = list(rotation_90_input(augmented_model_input, n_rotations))

            pred = model.predict_step(augmented_model_input)
            pred = [tensor.numpy() for tensor in pred]

            if n_rotations:
                pred = rotation_90_output(pred, 4 - n_rotations)
            if apply_horizontal_flip:
                pred = horizontal_flip_output(pred)

            preds.append(pred)

    return average_predictions(preds)


def average_predictions(preds):
    return [np.mean([pred[idx] for pred in preds], axis=0) for idx in range(len(preds[0]))]


def add_agent_id_to_features(features, model, agent_to_imitate_idx):
    ohe_size = model.input_shape[1][-1] - features.shape[-1]
    ohe = np.zeros((1, ohe_size), dtype=np.float32)
    ohe[..., agent_to_imitate_idx] = 1
    features = np.concatenate([features, ohe], axis=-1)
    return features


def agent(observation, configuration):
    ret = make_input(observation)
    board, features = ret[:2]
    features = add_agent_id_to_features(features, models[0], agent_to_imitate_idx=0)
    model_input = [expand_board_size_adding_zeros(np.expand_dims(board, axis=0)),
                   np.expand_dims(features, axis=0)]
    preds = [predict_with_data_augmentation(model, model_input) for model in models]
    preds = average_predictions(preds)
    preds = [crop_board_to_original_size(pred, observation) for pred in preds]
    active_unit_to_position, active_city_to_position, unit_to_position, city_to_position = ret[2:]
    action_kwargs = dict(action_threshold=0.2, policy='greedy')
    mask_threshold = 0.2

    unit_action, unit_policy = preds[0][0], preds[1][0]
    unit_policy *= unit_action > mask_threshold
    actions = create_actions_for_units_from_model_predictions(
        unit_policy, active_unit_to_position, unit_to_position, observation,
        set(city_to_position.keys()), **action_kwargs)

    city_action, city_policy = preds[2][0], preds[3][0]
    city_policy *= city_action > mask_threshold
    actions += create_actions_for_cities_from_model_predictions(
        city_policy, active_city_to_position, len(city_to_position) - len(unit_to_position),
        **action_kwargs)
    return actions



