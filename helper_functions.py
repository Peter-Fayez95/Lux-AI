#
#
# This module contains helper functions that can be used over all classes
#
#


import logging
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
    neighbours = []
    # logging.info(f"Cell before Translation is {cell}")
    # logging.info(f"Cell before Translation is {cell}")
    for dir in DIRECTIONS:
        pos = deepcopy(cell.pos)
        pos = pos.translate(dir, 1)

        if inside_map(pos, gamestate.map.width, gamestate.map.height):
            translated_cell = gamestate.map.get_cell(pos.x, pos.y)
            # logging.info(f"Translated Cell in {dir} is {pos.translate(dir, 1)}")

            neighbours.append(translated_cell)
    return neighbours


def get_cell_neighbours_eight(cell: Cell, gamestate):
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