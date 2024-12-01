#
#
# This module contains helper functions that can be used over all classes
#
#
from lux.game_constants import GAME_CONSTANTS
from typing import List

import logging
import math
from copy import deepcopy
from functools import cmp_to_key

from lux.game_map import Cell, Position, Resource
from lux.constants import Constants
from lux.game_objects import Unit

DIRECTIONS = Constants.DIRECTIONS
DIRECTIONS = [DIRECTIONS.NORTH, DIRECTIONS.EAST, DIRECTIONS.SOUTH, DIRECTIONS.WEST]


logging.basicConfig(filename="helper_functions.log", level=logging.INFO)

# TODO: Add unittests for this module

def inside_map(x, y, width, height):
    '''
    Check if the cell(x, y) is inside the map
    '''
    return (0 <= x < width) and (0 <= y < height)

def inside_map(pos: Position, width, height):
    return (0 <= pos.x < width) and (0 <= pos.y < height)

def same_resource(cell1 : Cell, cell2 : Cell) -> bool:
    return cell1.resource.type == cell2.resource.type


def cells_comparator_as_pair(cell1: Cell, cell2: Cell):
    '''
    Comparator for cells as a pair
    '''
    cell1 = [cell1.pos.x, cell1.pos.y]
    cell2 = [cell2.pos.x, cell2.pos.y]

    if cell1 < cell2:
        return -1
    else:
        return 1
    
def get_cell_neighbours_four(cell: Cell, gamestate):
    '''
    Get Cells Four Neighbours
    '''
    neighbours = []
    for dir in DIRECTIONS:
        pos = deepcopy(cell.pos)
        pos = pos.translate(dir, 1)

        if inside_map(pos, gamestate.map.width, gamestate.map.height):
            translated_cell = gamestate.map.get_cell(pos.x, pos.y)

            neighbours.append(translated_cell)
    return neighbours


def get_cell_neighbours_eight(cell: Cell, gamestate):
    '''
    Get Cells Eight Neighbours
    '''
    neighbours = get_cell_neighbours_four(cell, gamestate)

    dir1 = 0
    dir2 = 1

    for i in range(len(DIRECTIONS)):
        pos = deepcopy(cell.pos)
        pos = pos.translate(DIRECTIONS[dir1], 1)
        pos = pos.translate(DIRECTIONS[dir2], 1)
        
        dir1 = (dir1 + 1) % len(DIRECTIONS)
        dir2 = (dir2 + 1) % len(DIRECTIONS)

        if inside_map(pos, gamestate.map.width, gamestate.map.height):

            translated_cell = gamestate.map.get_cell(pos.x, pos.y)

            neighbours.append(translated_cell)
    
    return neighbours


def get_nearest_position(C: Position, cells: List[Position]):
    '''
    Given a cell `C` 
    Return the smallest distance and cell to it from a list of cells 
    '''
    nearest_position = None
    smallest_distance = math.inf
    # logging.warning(f"cells: {cells}")
    # logging.warning(f"C type: {type(C)}")
    # C = Position(C[0], C[1])


    for cell in cells:
        cell = Position(cell[0], cell[1])
        current_distance = C.distance_to(cell)
        
        if current_distance < smallest_distance:
            smallest_distance = current_distance
            nearest_position = cell

    return nearest_position, smallest_distance

def get_unit_by_id(id, player) -> Unit:
    for unit in player.units:
        if unit.id == id:
            return unit
        

def get_perimeter(cells, game_state):
    distinct_cells = set()
    for cell in cells:
        # logging.info(f"CELL: [{cell.pos.x, cell.pos.y}]")
        for neighbour in get_cell_neighbours_four(cell, game_state):
            
            if not neighbour.has_resource():
                distinct_cells.add((neighbour.pos.x, neighbour.pos.y))

    
    # distinct_cells = sorted(list(distinct_cells))
    return distinct_cells
        


def get_build_position_score(game_state, opponent, pos, center):
    travel_distance = center.distance_to(pos)
    travel_distance_score = 100 / ((travel_distance ** 2) + 1)

    opponent_distances = []
    for unit in opponent.units:
        distance = pos.distance_to(unit.pos)
        opponent_distances.append(distance)

    opponent_distance_score = (10 * len(opponent.units)) \
        / (sum(opponent_distances) + 1)

    perimeter = get_perimeter(
        [game_state.map.get_cell_by_pos(pos)],
        game_state
    )

    perimeter_score = 0
    for p in perimeter:
        cell = game_state.map.get_cell_by_pos(p)
        if cell.citytile is not None:
            perimeter_score += 2

    final_score = perimeter_score + opponent_distance_score \
        + travel_distance_score

    return final_score


def get_important_positions(game_state, opponent, available_targets, units):

    sum_x = sum([unit.pos.x for unit in units])
    sum_y = sum([unit.pos.y for unit in units])

    mean_x = sum_x / len(units)
    mean_y = sum_y / len(units)

    center = Position(mean_x, mean_y)

    def compare(pos1, pos2):
        return pos2[0] - pos1[0]

    pos_score_vector = []


    for pos in available_targets:
        score = get_build_position_score(game_state, opponent, pos, center)

        pos_score_vector.append([score, pos])

    pos_score_vector.sort(key=cmp_to_key(compare))

    return [pos_score[1] for pos_score in pos_score_vector][:len(units)]

def get_directions(src, dest):
    directions = []
    if dest.y - src.y < 0:
        directions.append(DIRECTIONS.NORTH)
    if dest.y - src.y > 0:
        directions.append(DIRECTIONS.SOUTH)
    if dest.x - src.x > 0:
        directions.append(DIRECTIONS.EAST)
    if dest.x - src.x < 0:
        directions.append(DIRECTIONS.WEST)
    return directions

def negotiate_actions(occupied_positions, requested_movements):
    '''
    This is just a simple heuristics.
    We prioritize unit that has only one direction to go.
    Currently, the unit does not have intelligence to make it way around
    and obstacle. If there is an obstacle, he/she simple waits till
    the obstacle is gone. More research is needed.
    '''

    # TO-DO make it more efficient
    # SORT UNIT BY PRIORTIY HEURISTICS
    actions = []

    # unmovable_units or obstacles
    for requested_movement in requested_movements:
        for movement in requested_movement['movements']:
            if (movement['next_pos'].x, movement['next_pos'].y) \
                    not in occupied_positions:
                break

            occupied_positions.add(
                (
                    requested_movement['unit'].pos.x,
                    requested_movement['unit'].pos.y
                )
            )
            requested_movement['approved'] = False

    for requested_movement in requested_movements:
        if len(requested_movement['movements']) == 1:
            movement = requested_movement['movements'][0]
            if (movement['next_pos'].x, movement['next_pos'].y) \
                    not in occupied_positions:
                actions.append(
                    requested_movement['unit'].move(movement['direction'])
                )
                occupied_positions.add(
                    (movement['next_pos'].x, movement['next_pos'].y)
                )
                requested_movement['approved'] = True
            else:
                occupied_positions.add(
                    (requested_movement['unit'].pos.x,
                     requested_movement['unit'].pos.y)
                )

    for requested_movement in requested_movements:
        if len(requested_movement['movements']) > 1:
            movements = requested_movement['movements']
            for movement in movements:
                if (movement['next_pos'].x, movement['next_pos'].y) \
                        not in occupied_positions:
                    actions.append(
                        requested_movement['unit'].move(movement['direction'])
                    )
                    occupied_positions.add(
                        (movement['next_pos'].x, movement['next_pos'].y)
                    )
                    requested_movement['approved'] = True
                    break

        if not requested_movement['approved']:
            occupied_positions.add(
                (
                    requested_movement['unit'].pos.x,
                    requested_movement['unit'].pos.y
                )
            )

    return actions

def get_enemy_coverage(cells, opponent, opponent_id):
    '''
    This returns the number of opponent units and
    the number of citytiles in a list of cells given.
    '''
    opponent_citytiles = []
    for cell in cells:
        if cell.citytile is not None:
            if cell.citytile.team == opponent_id:
                opponent_citytiles.append(cell.citytile)

    cell_positions = [cell.pos for cell in cells]
    opponent_units = []
    for unit in opponent.units:
        pos = next(
            (p for p in cell_positions if p.equals(unit.pos)),
            None,
        )

        if pos is not None:
            opponent_units.append(unit)

    return opponent_citytiles, opponent_units



def get_closest_cluster_by_centroid(citytile, cluster_dict):
    '''
    We sort the clusters by the distance to the cluster center
    '''
    closest_distance = math.inf
    closest_cluster = None

    for id, cluster in cluster_dict.items():
        distance = citytile.pos.distance_to(
            cluster.get_centroid()
        )
        if distance < closest_distance:
            closest_distance = distance
            closest_cluster = cluster

    return closest_cluster, closest_distance

def get_citytile_score(
    cluster,
    game_state,
    player_id,
    opponent,
    opponent_id
):
    '''
    A simple mathematical model to calculate a citytile should build a worker.
    '''
    # directly proportional
    resource_cell_score = len(cluster.resource_cells)
    fuel_score = cluster.get_total_fuel() / 100

    perimeter = get_perimeter(
            cluster.resource_cells,
            game_state        
        )
    perimeter_score = len(perimeter)

    opponent_citytiles, opponent_units = get_enemy_coverage(
        [game_state.map.get_cell_by_pos(Position(pos[0], pos[1])) for pos in perimeter],
        opponent,
        opponent_id,
    )
    opponent_workers_score = len(opponent_units) + 1
    opponent_citytiles_score = len(opponent_citytiles) + 1

    # inversely proportional
    player_citytiles = []
    for p in perimeter:
        cell = game_state.map.get_cell_by_pos(Position(p[0], p[1]))
        if cell.citytile is not None:
            if cell.citytile.team == player_id:
                player_citytiles.append(cell.citytile)

    player_workers_score = 10 * len(cluster.units) + 1
    player_citytiles_score = len(player_citytiles) + 1

    no_player_unit_bonus = 10 if len(cluster.units) == 0 else 1

    numerator = resource_cell_score * fuel_score * perimeter_score * \
        no_player_unit_bonus * opponent_workers_score * \
        opponent_citytiles_score

    denominator = player_workers_score * player_citytiles_score

    citytile_score = numerator / (denominator + 1.1)

    return citytile_score

def get_city_actions(
    game_state,
    game_state_info,
    player,
    clusters_dict,
    player_id,
    opponent,
    opponent_id
):
    '''
    This is actually simple. We greedily build worker if possible.
    The only trick is if two citytiles can build only one worker,
    we decide which gets to build by calculating the score.
    '''
    actions = []
    units_capacity = sum([len(x.citytiles) for x in player.cities.values()])
    units_count = len(player.units)

    actionable_citytiles = []
    for city in player.cities.values():
        for citytile in city.citytiles:
            if citytile.can_act():
                actionable_citytiles.append(citytile)

    citytiles_to_be_sorted = []
    for citytile in actionable_citytiles:
        # We do not keep track of which cluster a citytile belongs to.
        # So, we need to find it here.
        closest_cluster, _ = get_closest_cluster_by_centroid(
            citytile,
            clusters_dict
        )
        citytile_score = 0
        if closest_cluster is not None:
            citytile_score = get_citytile_score(
                closest_cluster,
                game_state,
                player_id,
                opponent,
                opponent_id
            )

        citytiles_to_be_sorted.append({
            'citytile': citytile,
            'score': citytile_score
        })

    def compare(citytile1, citytile2):
        return citytile2['score'] - citytile1['score']

    sorted_citytiles = sorted(
        citytiles_to_be_sorted,
        key=cmp_to_key(compare)
    )

    for citytile in sorted_citytiles:
        if units_count < units_capacity and \
                game_state_info['turns_to_night'] > 4:
            actions.append(
                citytile['citytile'].build_worker()
            )
            units_count += 1
        else:
            if not player.researched_uranium():
                actions.append(
                    citytile['citytile'].research()
                )

    return actions


def update_game_stats(turn):
    MAX_DAYS = GAME_CONSTANTS['PARAMETERS']['MAX_DAYS']
    DAY_LENGTH = GAME_CONSTANTS['PARAMETERS']['DAY_LENGTH']
    NIGHT_LENGTH = GAME_CONSTANTS['PARAMETERS']['NIGHT_LENGTH']
    FULL_LENTH = DAY_LENGTH + NIGHT_LENGTH

    all_night_turns_lef = ((MAX_DAYS - 1 - turn) // FULL_LENTH + 1) \
        * NIGHT_LENGTH

    turns_to_night = (DAY_LENGTH - turn) % FULL_LENTH
    turns_to_night = 0 if turns_to_night > 30 else turns_to_night

    turns_to_dawn = FULL_LENTH - turn % FULL_LENTH
    turns_to_dawn = 0 if turns_to_dawn > 10 else turns_to_dawn

    is_day_time = turns_to_dawn == 0
    is_night_time = turns_to_night == 0

    if is_night_time:
        all_night_turns_lef -= (10 - turns_to_dawn)

    return {
        'all_night_turns_left': all_night_turns_lef,
        'turns_to_night': turns_to_night,
        'turns_to_dawn': turns_to_dawn,
        'is_day_time': is_day_time,
        'is_night_time': is_night_time
    }