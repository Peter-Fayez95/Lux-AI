from functools import cmp_to_key
import logging

from lux.game_map import Cell, Position
from lux.constants import Constants
from lux.game_constants import GAME_CONSTANTS
from helper_functions import cells_comparator_as_pair, get_cell_neighbours_four


class Cluster:
    '''
    The cluster is basically a connected component of resources
    Each cluster consists of only one type of resources (Wood / Coal / Uranium)

    clusterID       int             Representative Cell DSU Rank
    cells           List(Cells)     List of this cluster's cells
    '''

    def __init__(self, cluster_id, cells):
        self.clusterID = cluster_id
        self.cells = cells

    
    def get_perimeter(self, gamestate) -> list[Cell]:
        '''
        Get the cluster surronding cell from north, east, west, south
        These cells must be guarded with Units to guard the cluster
        '''
        distinct_cells = set()
        for cell in self.cells:
            logging.info(f"CELL: [{cell.pos.x, cell.pos.y}]")
            for neighbour in get_cell_neighbours_four(cell, gamestate):
                
                if not neighbour.has_resource():
                    distinct_cells.add((neighbour.pos.x, neighbour.pos.y))

        
        distinct_cells = sorted(list(distinct_cells))
        logging.critical(f"DISTINCT CELLS: {type(distinct_cells)}")
        

        # for cell in distinct_cells:
        #     logging.info(f"[{cell.pos.x}, {cell.pos.y}]")
        
        return distinct_cells
    


    def get_total_fuel(self) -> int:
        '''
        Get total cluster fuel
        '''
        FUEL_CONVERSION_RATE = GAME_CONSTANTS['PARAMETERS']['RESOURCE_TO_FUEL_RATE']

        def get_cell_fuel(cell: Cell):
            if cell.resource is None:
                return 0
            if cell.resource.type == Constants.RESOURCE_TYPES.WOOD:
                return cell.resource.amount * FUEL_CONVERSION_RATE['WOOD']
            if cell.resource.type == Constants.RESOURCE_TYPES.COAL:
                return cell.resource.amount * FUEL_CONVERSION_RATE['COAL']
            if cell.resource.type == Constants.RESOURCE_TYPES.URANIUM:
                return cell.resource.amount * FUEL_CONVERSION_RATE['URANIUM']
            return 0

        return sum([get_cell_fuel(cell) for cell in self.resource_cells])

