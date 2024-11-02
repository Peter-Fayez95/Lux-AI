import os
import numpy as np
from collections import defaultdict
from itertools import product
import torch
from lux.game import Game


path = '/kaggle_simulations/agent' if os.path.exists('/kaggle_simulations') else '.'
unit_model = torch.jit.load(f'{path}/unit_model.pth')
city_model = torch.jit.load(f'{path}/city_model.pth')
unit_model.eval()
city_model.eval()


def make_unit_input(obs, shift):
    cities = {}
    q, mod = divmod(obs['step'], 40)
    nights = 10 * (9 - q) - max(mod - 30, 0)
    
    b = np.zeros((18, 32, 32), dtype=np.float32)
    
    for update in obs['updates']:
        strs = update.split(' ')
        input_identifier = strs[0]
        
        if input_identifier == 'u':
            # Units
            team = int(strs[2])
            x = int(strs[4]) + shift
            y = int(strs[5]) + shift
            cooldown = float(strs[6])
            wood = int(strs[7])
            coal = int(strs[8])
            uranium = int(strs[9])
            idx = (team - obs['player']) % 2 * 3
            b[idx:idx + 3, x, y] = (
                1,
                cooldown / 6,
                min(wood + coal + uranium, 100) / 100
            )
        elif input_identifier == 'ct':
            # CityTiles
            team = int(strs[1])
            city_id = strs[2]
            x = int(strs[3]) + shift
            y = int(strs[4]) + shift
            idx = 6 + (team - obs['player']) % 2 * 2
            b[idx:idx + 2, x, y] = (
                1,
                cities[city_id]
            )
        elif input_identifier == 'r':
            # Resources
            r_type = strs[1]
            x = int(strs[2]) + shift
            y = int(strs[3]) + shift
            amt = int(strs[4])
            b[{'wood': 10, 'coal': 11, 'uranium': 12}[r_type], x, y] = amt / 800
        elif input_identifier == 'rp':
            # Research Points
            team = int(strs[1])
            rp = int(strs[2])
            b[13 + (team - obs['player']) % 2, :] = min(rp, 200) / 200
        elif input_identifier == 'c':
            # Cities
            city_id = strs[2]
            fuel = float(strs[3])
            lightupkeep = float(strs[4])
            cities[city_id] = min(fuel / lightupkeep, nights) / nights
        elif input_identifier == 'ccd':
            # Roads
            break
    
    # Day/Night Cycle
    b[15, :] = obs['step'] % 40 / 40
    # Turns
    b[16, :] = obs['step'] / 360
    # Map Size
    b[17, shift:32 - shift, shift:32 - shift] = 1

    return b


def make_city_input(obs, shift):
    cities = {}
    q, mod = divmod(obs['step'], 40)
    nights = 10 * (9 - q) - max(mod - 30, 0)
    
    b = np.zeros((16, 32, 32), dtype=np.float32)
    
    for update in obs['updates']:
        strs = update.split(' ')
        input_identifier = strs[0]
        
        if input_identifier == 'ct':
            # CityTiles
            team = int(strs[1])
            city_id = strs[2]
            x = int(strs[3]) + shift
            y = int(strs[4]) + shift
            cooldown = float(strs[5])
            idx = (team - obs['player']) % 2 * 3
            b[idx:idx + 3, x, y] = (
                1,
                cooldown / 10,
                cities[city_id]
            )
        elif input_identifier == 'u':
            # Units
            team = int(strs[2])
            x = int(strs[4]) + shift
            y = int(strs[5]) + shift
            b[6 + (team - obs['player']) % 2, x, y] = 1
        elif input_identifier == 'r':
            # Resources
            r_type = strs[1]
            x = int(strs[2]) + shift
            y = int(strs[3]) + shift
            amt = int(strs[4])
            b[{'wood': 8, 'coal': 9, 'uranium': 10}[r_type], x, y] = amt / 800
        elif input_identifier == 'rp':
            # Research Points
            team = int(strs[1])
            rp = int(strs[2])
            b[11 + (team - obs['player']) % 2, :] = min(rp, 200) / 200
        elif input_identifier == 'c':
            # Cities
            city_id = strs[2]
            fuel = float(strs[3])
            lightupkeep = float(strs[4])
            cities[city_id] = min(fuel / lightupkeep, nights) / nights
        elif input_identifier == 'ccd':
            # Roads
            break
    
    # Day/Night Cycle
    b[13, :] = obs['step'] % 40 / 40
    # Turns
    b[14, :] = obs['step'] / 360
    # Map Size
    b[15, shift:32 - shift, shift:32 - shift] = 1

    return b


game_state = None
def get_game_state(observation):
    global model, game_state
    
    if observation["step"] == 0:        
        game_state = Game()
        game_state._initialize(observation["updates"])
        game_state._update(observation["updates"][2:])
        game_state.id = observation["player"]
    else:
        game_state._update(observation["updates"])
    return game_state


def transform(x, hflip, vflip):
    # Flip vertically
    if vflip:
        x = np.flip(x, axis=2).copy()
    # Flip horizontally
    if hflip:
        x = np.flip(x, axis=3).copy()
    return x


def predict(model, states):
    policies = []
    for h, v in product(range(2), repeat=2):
        x = transform(states, h, v)        
        with torch.no_grad():
            pred = model(torch.from_numpy(x)).numpy()

        if v:
            pred = np.flip(pred, axis=2)
            if pred.shape[1] == 6:
                pred = pred[:, [0,1,2,4,3,5]]
        if h:
            pred = np.flip(pred, axis=3)
            if pred.shape[1] == 6:
                pred = pred[:, [0,2,1,3,4,5]]
    
        policies.append(pred)
    
    return np.mean(policies, axis=0)


def in_city(pos):    
    try:
        city = game_state.map.get_cell_by_pos(pos).citytile
        return city is not None and city.team == game_state.id
    except:
        return False


unit_actions = [('move', 'c'), ('move', 'n'), ('move', 's'), ('move', 'w'), ('move', 'e'), ('build_city',)]
city_actions = [None, 'research', 'build_worker']
def call_func(obj, method, args=[]):
    return getattr(obj, method)(*args)


def get_action(policy, unit, shift, dest):
    if game_state.turn % 40 == 30 and not in_city(unit.pos):
        adjacent_citytiles = []
        for act in unit_actions[1:-1]:
            direction = act[1]
            pos = unit.pos.translate(direction, 1)
            if in_city(pos):
                adjacent_citytiles.append(
                    (game_state.map.get_cell_by_pos(pos).citytile, direction)
                )
        
        if len(adjacent_citytiles) > 0:
            cities = game_state.players[unit.team].cities
            adjacent_citytiles.sort(key=lambda ac: bcity_timestamp[str(ac[0].pos)])
            adjacent_citytiles.sort(key=lambda ac: len(cities[ac[0].cityid].citytiles), reverse=True)
            citytile, direction = adjacent_citytiles[0]
            return unit.move(direction), citytile.pos
    
    for label in np.argsort(policy[:, unit.pos.x + shift, unit.pos.y + shift])[::-1]:
        act = unit_actions[label]
        pos = unit.pos.translate(act[-1], 1) or unit.pos
        if pos not in dest or in_city(pos):
            return call_func(unit, *act), pos 
            
    return unit.move('c'), unit.pos


bcity_timestamp = defaultdict(int)
def agent(observation, configuration):
    global game_state
    
    game_state = get_game_state(observation)
    shift = (32 - game_state.map.width) // 2
    player = game_state.players[observation.player]
    actions = []
    
    # Worker Actions
    states = np.array([make_unit_input(observation, shift)])
    policy = predict(unit_model, states)[0]
    dest = []
    for i, unit in enumerate(player.units):
        if unit.can_act():
            action, pos = get_action(policy, unit, shift, dest)
            if action == unit.build_city():
                bcity_timestamp[str(pos)] = game_state.turn * 100 + i

            actions.append(action)
            dest.append(pos)
    
    # City Actions
    states = np.array([make_city_input(observation, shift)])
    policy = predict(city_model, states)[0]
    citytiles = [
        citytile
        for city in player.cities.values()
        for citytile in city.citytiles
        if citytile.can_act()
    ]
    citytiles.sort(
        key=lambda ct: bcity_timestamp[str(ct.pos)]
    )
    for citytile in citytiles:
        action = city_actions[
            np.argmax(policy[:, citytile.pos.x + shift, citytile.pos.y + shift])
        ]
        if action is not None:
            actions.append(call_func(citytile, action))

    return actions
