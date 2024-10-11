import logging
from copy import deepcopy


from lux.game_map import Cell
from lux.constants import Constants

DIRECTIONS = Constants.DIRECTIONS
DIRECTIONS = [DIRECTIONS.NORTH, DIRECTIONS.SOUTH, DIRECTIONS.EAST, DIRECTIONS.WEST]


# TODO: Add unittests for this module

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
    logging.info(f"Cell before Translation is {cell}")
    # logging.info(f"Cell before Translation is {cell}")
    for dir in DIRECTIONS:
        pos = deepcopy(cell.pos)
        pos = pos.translate(dir, 1)
        translated_cell = gamestate.map.get_cell(pos.x, pos.y)
        # logging.info(f"Translated Cell in {dir} is {pos.translate(dir, 1)}")

        neighbours.append(translated_cell)
    return neighbours