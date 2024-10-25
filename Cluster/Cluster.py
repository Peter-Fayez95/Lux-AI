from functools import cmp_to_key
import logging
import math

from lux.game_map import Cell, Position
from lux.constants import Constants
from lux.game_constants import GAME_CONSTANTS
from helper_functions import cells_comparator_as_pair, get_cell_neighbours_four, \
                            inside_map, get_nearest_position

from Weights.Cluster import cluster_weights

class Cluster:
    '''
    The cluster is basically a connected component of resources
    Each cluster consists of only one type of resources (Wood / Coal / Uranium)

    clusterID       int             Representative Cell DSU Rank
    cells           List(Cells)     List of this cluster's cells
    units           List(Str)       List of this cluster's units (workers / carts)
    '''

    def __init__(self, cluster_id, cells):
        self.clusterID = cluster_id
        self.resource_cells = cells
        self.units = []

    
    def get_perimeter(self, gamestate) -> list[Cell]:
        '''
        Get the cluster surronding cell from north, east, west, south
        These cells must be guarded with Units to guard the cluster
        '''
        distinct_cells = set()
        for cell in self.resource_cells:
            # logging.info(f"CELL: [{cell.pos.x, cell.pos.y}]")
            for neighbour in get_cell_neighbours_four(cell, gamestate):
                
                if not neighbour.has_resource():
                    distinct_cells.add((neighbour.pos.x, neighbour.pos.y))

        
        distinct_cells = sorted(list(distinct_cells))
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
    

    def get_centroid(self):
        sum_x = sum([cell.pos.x for cell in self.resource_cells])
        sum_y = sum([cell.pos.y for cell in self.resource_cells])
        k = len(self.resource_cells)

        if k == 0:
            return Position(math.inf, math.inf)
        
        return Position(round(sum_x / k), round(sum_y / k))
    

    def get_cluster_area(self, gamestate):
        '''
        Get whole cluster area
        cluster_area represents all of the cluster cells (including its perimeter)
        '''
        area = self.resource_cells
        area.extend(self.get_perimeter(gamestate))

        return area



    def get_all_workers(self, player):
        '''
        Return all worker currently in the cluster area
        TODO: Refactor this function to reduce time complexity
        '''
        pass
        # player_workers = []

        # for unit in self.units: # Str
        #     if unit in player_workers:
                
    


    def get_cluster_score_for_worker(self, worker, gamestate, player_id):
        '''
        Check the score of this cluster for worker
        If the score is high enough, the worker should work for this cluster
        '''
        pass
        opponent_id = 1 - player_id

        if len(self.resource_cells) == 0:
            return 0

        perimeter = self.get_perimeter(gamestate)
        nearest_position, distance = get_nearest_position(worker.pos, perimeter)

        # cluster_area represents all of the cluster cells (including its perimeter)
        cluster_area = [
            gamestate.map.get_cell_by_pos(pos) for pos in perimeter
        ]

        cluster_area.extend(self.resource_cells)
        
        
        # opponent_citytiles, opponent_units = SpyService.get_enemy_coverage(
        #     perimeter_cells,
        #     opponent,
        #     opponent_id,
        # )

        # And how many of the perimeter are our citytiles.
        player_citytiles = []
        for cell in perimeter:
            cell = gamestate.map.get_cell_by_pos(cell)
            if cell.citytile is not None:
                if cell.citytile.team == player_id:
                    player_citytiles.append(cell.citytile)

        cluster_score = \
            distance * cluster_weights['DISTANCE'] + \
            len(self.resource_cells) * cluster_weights['RESOURCE_CELLS'] + \
            len(perimeter) * cluster_weights['PERIMETER'] + \
            len(player_citytiles) * cluster_weights['OUR_CITYTILES'] + \
            len(self.units) * cluster_weights['PLAYER_UNITS']
            # len(opponent_units) * cluster_weights['OPPONENT_UNITS'] + \
            # len(opponent_citytiles) * cluster_weights['OPPONENT_CITYTILES']

        return cluster_score
        

