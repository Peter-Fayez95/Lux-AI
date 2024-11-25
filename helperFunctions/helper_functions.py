#
#
# This module contains helper functions that can be used over all classes
#
#


import logging
import math
from copy import deepcopy
from functools import cmp_to_key

from lux.game_map import Cell, Position, Resource
from lux.constants import Constants
from lux.game_objects import Unit

DIRECTIONS = Constants.DIRECTIONS
DIRECTIONS = [DIRECTIONS.NORTH, DIRECTIONS.EAST, DIRECTIONS.SOUTH, DIRECTIONS.WEST]


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


def get_nearest_position(C, cells):
    '''
    Given a cell `C` 
    Return the smallest distance and cell to it from a list of cells 
    '''
    nearest_position = None
    smallest_distance = math.inf

    for cell in cells:
        current_distance = C.pos.distance_to(cell.pos)
        
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

