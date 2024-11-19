from functools import cmp_to_key
import logging
import math

from lux.game_map import Cell, Position
from lux.constants import Constants
from lux.game_constants import GAME_CONSTANTS
from helperFuncions.helper_functions import cells_comparator_as_pair, get_cell_neighbours_four, \
                            inside_map, get_nearest_position, get_unit_by_id, get_important_positions

from Resources.resourceService import get_resources_from_cells

from Weights.Cluster import cluster_weights
from Missions import Mission, MissionController
from Missions.constants import BUILD_TILE, GUARD_CLUSTER


class Cluster:
    '''
    The cluster is basically a connected component of resources
    Each cluster consists of only one type of resources (Wood / Coal / Uranium)

    clusterID           int             Representative Cell DSU Rank
    cells               List(Cells)     List of this cluster's cells
    units               List(Str)       List of this cluster's units (workers / carts)
    perimeter           List(Cells)     List of this cluster's perimeter cells
    exposed_perimeter   List(Cells)     List of this cluster's perimeter cells without citytiles
    missions            List(Mission)   List of this cluster's missions
    '''

    def __init__(self, resource_type, cluster_id, cells):
        self.resource_type = resource_type
        self.clusterID = cluster_id
        self.resource_cells = cells
        self.units = []
        self.perimeter = []
        self.exposed_perimeter = []
        self.missions = []
    
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

        
        # distinct_cells = sorted(list(distinct_cells))
        return distinct_cells
    


    def get_total_fuel(self) -> int:
        '''
        Get total cluster fuel
        '''
        
        FUEL_CONVERSION_RATE = GAME_CONSTANTS['PARAMETERS']['RESOURCE_TO_FUEL_RATE']
        
        def get_cell_fuel(cell: Cell):
            if not cell.has_resource():
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

    def add_unit(self, unit_id):
        '''
        Add a unit to the cluster
        '''
        self.units.append(unit_id)
                
    def remove_unit(self, unit_id):
        '''
        Remove a unit from the cluster
        '''
        try:
            self.units.remove(unit_id)
        except ValueError:
            pass


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
        


    def update_cluster(self, game_state, player):
        '''
        Update this cluster
        1- Update Resource Cells (Some cells get consumed)
        2- Update Cluster Units (Some units die)
        3- Update Perimeter and Exposed Perimeter
        '''

        # Update Cluster Resource Cells
        new_resource_cells = get_resources_from_cells(game_state, self.resource_cells)
        self.resource_cells = new_resource_cells

        # Update Cluster Units
        player_all_units = set(unit.id for unit in player.units)

        cluster_units = set(unit_id for unit_id in self.units if unit_id in player_all_units)

        self.units = cluster_units

        # Update Perimeter
        self.perimeter = self.get_perimeter(game_state)

        # Update Perimeter Cells without CityTiles
        self.exposed_perimeter = [
            (x, y) for (x, y) in self.perimeter
            if game_state.map.get_cell(x, y).citytile is not None and
                not game_state.map.get_cell(x, y).has_resource()
        ]

    def remove_finished_missions(self, game_state):
        '''
        Remove all finished missions from this cluster
        
        1- Remove all finished BUILD_TILE missions
        2- Remove all finished GUARD_CLUSTER missions

        '''
        MissionController.remove_finished_tile_missions(self.missions, game_state)
        MissionController.remove_finished_guard_missions(self.missions, game_state)

    def remove_missions_with_no_units(self):
        '''
        Remove all missions with no responsible units
        '''
        MissionController.remove_missions_with_no_units(self.missions, self.units)


    def update_missions(self, game_state):
        '''
        Update the missions for this cluster

        1- Remove all finished missions
        2- Remove all missions with no responsible units
        3- Issue new missions:
            - If the cluster has no units, issue a BUILD_TILE mission (First Priority)
            - If the cluster has units, issue a GUARD_CLUSTER mission (Second Priority)
        '''
        self.remove_finished_missions(game_state)
        self.remove_missions_with_no_units()

        units_without_missions = [
            unit_id for unit_id in self.units if unit_id not in 
                [mission.responsible_unit.id for mission in self.missions]
        ]

        cells_without_tiles = self.exposed_perimeter
        build_mission_count = 0

        for unit_id in units_without_missions:
            if build_mission_count == len(cells_without_tiles):
                break

            self.missions[unit_id] = Mission(
                unit_id,
                BUILD_TILE,
                cells_without_tiles[build_mission_count]
            )

            build_mission_count += 1

        units_without_missions = [
            unit_id for unit_id in self.units if unit_id not in 
                [mission.responsible_unit.id for mission in self.missions]
        ]

        guard_mission_count = 0
        for unit_id in units_without_missions:
            if guard_mission_count == len(self.resource_cells):
                break

            self.missions.append(Mission(
                unit_id,
                GUARD_CLUSTER,
                self.resource_cells[guard_mission_count].pos  
            ))
            guard_mission_count += 1

        # If we have more workers than required, we release them.
        released_units = [
            unit_id for unit_id in self.units if unit_id not in 
                [mission.responsible_unit.id for mission in self.missions]
        ]

        for unit_id in released_units:
            self.remove_unit(unit_id)

        # If cluster resources are depleted, no use for its units.
        if len(self.resource_cells) == 0:
            self.units = []
            self.missions = []


    def assign_targets_to_missions(self, game_state, player, opponent, mission_type):
        
        units = []

        for mission in self.missions:
            if mission.mission_type == mission_type:
                units.append(get_unit_by_id(mission.responsible_unit.id, player))

        if len(units) == 0:
            return
        
        target_positions = []

        if mission_type == BUILD_TILE:
            target_positions.extend(get_important_positions(game_state, opponent, 
            self.exposed_perimeter, units))

        
        if mission_type == GUARD_CLUSTER:
            target_positions.extend(get_important_positions(
                game_state, 
                opponent, 
                [cell.pos for cell in self.resource_cells], 
                units))
        
        if len(target_positions) == 0:
            return
        
        mission_controller = MissionController()

        missions = mission_controller.negotiate_missions(
            self.missions,
            units,
            target_positions
        )

        self.missions = missions