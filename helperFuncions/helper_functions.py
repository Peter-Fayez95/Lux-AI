#
#
# This module contains helper functions that can be used over all classes
#
#


import logging
import math
from copy import deepcopy


from lux.game_map import Cell, Position, Resource
from lux.constants import Constants

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