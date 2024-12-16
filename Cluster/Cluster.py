from functools import cmp_to_key
import logging
import math

from lux.game_map import Cell, Position
from lux.constants import Constants
from collections import defaultdict
from lux.game_constants import GAME_CONSTANTS
from helperFunctions.helper_functions import *
from lux import annotate


from Resources.resourceService import get_resources_from_cells

from Weights.Cluster import cluster_weights
from Missions.Mission import Mission
from Missions.MissionController import *
from Missions.constants import BUILD_TILE, GUARD_CLUSTER, EXPLORE

logging.basicConfig(filename='cluster.log', level=logging.INFO)


class Cluster:
    '''
    The cluster is basically a connected component of resources
    Each cluster consists of only one type of resources (Wood / Coal / Uranium)

    clusterID           int                     Representative Cell DSU Rank
    cells               List(Cells)             List of this cluster's cells
    units               List(Str)               List of this cluster's units (workers / carts)
    perimeter           List(Cells)             List of this cluster's perimeter cells
    exposed_perimeter   List(Cells)             List of this cluster's perimeter cells without citytiles
    missions            Dict(Str -> Mission)    Dictionary of this cluster's missions
    '''

    def __init__(self, resource_type, cluster_id, cells):
        self.resource_type = resource_type
        self.clusterID = cluster_id
        self.resource_cells = cells
        self.units = []
        self.perimeter = []
        self.exposed_perimeter = []
        self.missions = defaultdict(Mission)
    
    def get_perimeter(self, gamestate) -> list[Cell]:
        '''
        Get the cluster surronding cell from north, east, west, south
        These cells must be guarded with Units to guard the cluster
        '''
        perimeter_dict = defaultdict()
        cells = self.resource_cells.copy()

        for tile in cells:
            n = tile.pos.translate('n', 1)
            s = tile.pos.translate('s', 1)
            e = tile.pos.translate('e', 1)
            w = tile.pos.translate('w', 1)

            sides = [n, s, e, w]

            for side in sides:
                side_tile = next(
                    (t for t in cells if t.pos.equals(side)),
                    None
                )

                if side_tile is None:
                    if (side.x >= 0 and side.x < gamestate.map.width) and \
                            (side.y >= 0 and side.y < gamestate.map.height):
                        perimeter_dict[str(side.x) + str(side.y)] = side

        return list(perimeter_dict.values())
    


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


    def get_cluster_score_for_worker(self, worker, gamestate, player_id, opponent):
        '''
        Check the score of this cluster for worker
        If the score is high enough, the worker should work for this cluster
        '''
        opponent_id = 1 - player_id

        if len(self.resource_cells) == 0:
            return 0

        # perimeter = self.get_perimeter(gamestate)
        nearest_position, distance = get_nearest_position(worker.pos, self.exposed_perimeter)

        # cluster_area represents all of the cluster cells (including its perimeter)
        cluster_area = [
            gamestate.map.get_cell_by_pos(pos) for pos in self.perimeter
        ]

        cluster_area.extend(self.resource_cells)
        
        
        opponent_tiles, opponent_units = get_enemy_tiles(
            cluster_area,
            opponent,
            opponent_id,
        )

        # And how many of the perimeter are our citytiles.
        player_citytiles = []
        for cell in self.perimeter:
            cell = gamestate.map.get_cell_by_pos(cell)
            if cell.citytile is not None:
                if cell.citytile.team == player_id:
                    player_citytiles.append(cell.citytile)

        cluster_score = \
            distance * cluster_weights['DISTANCE'] + \
            len(self.resource_cells) * cluster_weights['RESOURCE_CELLS'] + \
            len(self.perimeter) * cluster_weights['PERIMETER'] + \
            len(player_citytiles) * cluster_weights['OUR_CITYTILES'] + \
            len(self.units) * cluster_weights['OUR_UNITS'] + \
            len(opponent_units) * cluster_weights['OPPONENT_UNITS'] + \
            len(opponent_tiles) * cluster_weights['OPPONENT_CITYTILES']

        return cluster_score
        


    def update_cluster(self, game_state, player):
        '''
        Update this cluster
        1- Update Resource Cells (Some cells get consumed)
        2- Update Cluster Units (Some units die)
        3- Update Perimeter and Exposed Perimeter
        ''' 

        # Update Cluster Resource Cells
        new_resource_cells = get_resources_from_cells(game_state, [c.pos for c in self.resource_cells])
        self.resource_cells = new_resource_cells

        # Update Cluster Units
        player_all_units = list(unit.id for unit in player.units)

        cluster_units = list(unit_id for unit_id in self.units if unit_id in player_all_units)

        self.units = cluster_units

        # Update Perimeter
        self.perimeter = self.get_perimeter(game_state)
        # print("PERIMETER: ", self.perimeter[0][0], self.perimeter[0][1])

        # Update Perimeter Cells without CityTiles
        exposed_perimeter = [
        p for p in self.perimeter
            if game_state.map.get_cell_by_pos(p).citytile is None and
            not game_state.map.get_cell_by_pos(p).has_resource()
        ]
        self.exposed_perimeter = exposed_perimeter
        # print("EXPOSED PERIMETER: ", self.exposed_perimeter)

    def remove_finished_tile_missions(self, game_state):
        '''
        Remove all finished BUILD_TILE missions
        '''
        missions_list = self.missions.copy()

        for unit, mission in self.missions.items():
            if mission.target_pos is None:
                continue

            if mission.mission_type == BUILD_TILE:
                cell = game_state.map.get_cell_by_pos(mission.target_pos)
                if cell.citytile is not None:
                    del missions_list[unit]

        return missions_list
        
    def remove_finished_explore_missions(self, player):
        '''
        Remove all finished EXPLORE missions
        '''
        missions_list = self.missions.copy()

        for _, mission in self.missions.items():
            if mission.target_pos is None:
                continue

            if mission.mission_type == EXPLORE:
                unit = mission.responsible_unit
                if unit.pos.equals(mission.target_pos):
                    del missions_list[_]
                
        return missions_list

    def remove_finished_guard_missions(self, player):
        '''
        Remove all finished GUARD_CLUSTER missions
        '''
        missions_list = self.missions.copy()

        for _, mission in self.missions.items():
            if mission.target_pos is None:
                continue

            if mission.mission_type == GUARD_CLUSTER:
                unit = mission.responsible_unit
                if unit.pos.equals(mission.target_pos):
                    del missions_list[_]
        
        return missions_list


    def remove_finished_missions(self, game_state, player):
        '''
        Remove all finished missions from this cluster
        
        1- Remove all finished BUILD_TILE missions
        2- Remove all finished EXPLORE missions
        3- Remove all finished GUARD_CLUSTER missions

        '''
        self.missions = self.remove_finished_tile_missions(game_state)
        self.missions = self.remove_finished_explore_missions(player)
        self.missions = self.remove_finished_guard_missions(player)

    def remove_missions_with_no_units(self, units):
        '''
        Remove all missions with no responsible units
        '''
        missions_list = self.missions.copy()
        
        for unit in self.missions:
            if unit not in units:
                del missions_list[unit]
        
        return missions_list


    def update_missions(self, game_state, player):
        '''
        Update the missions for this cluster

        1- Remove all missions with no responsible units
        2- Remove all finished missions
        3- Issue new missions:
            - If the cluster has no units, issue a BUILD_TILE mission (First Priority)
            - If the cluster has units, issue a GUARD_CLUSTER mission (Second Priority)
        '''
        self.missions = self.remove_missions_with_no_units(self.units)
        self.remove_finished_missions(game_state, player)
        
        missions_list = self.missions.copy()

        units_without_missions = [
            unit_id for unit_id in self.units if unit_id not in missions_list
        ]

        cells_without_tiles = self.exposed_perimeter
        # print("sadasdsdsadsadsad", cells_without_tiles)
        build_mission_count = 0

        for unit_id in units_without_missions:
            if build_mission_count == len(cells_without_tiles):
                break

            # pos = Position(cells_without_tiles[build_mission_count][0], cells_without_tiles[build_mission_count][1])

            missions_list[unit_id] = Mission(
                mission_type=BUILD_TILE,
            )
            build_mission_count += 1

        units_without_missions = [
            unit_id for unit_id in self.units if unit_id not in missions_list
        ]

        guard_mission_count = 0
        for unit_id in units_without_missions:
            if guard_mission_count == len(self.resource_cells):
                break

            missions_list[unit_id] = Mission(
                mission_type=GUARD_CLUSTER,
            )

            guard_mission_count += 1

        # If we have more workers than required, we release them.
        released_units = [
            unit_id for unit_id in self.units if unit_id not in missions_list
        ]

        for unit_id in released_units:
            self.remove_unit(unit_id)

        # If cluster resources are depleted, no use for its units.
        if len(self.resource_cells) == 0:
            self.units = []

        self.missions = missions_list


    def assign_targets_to_missions(self, game_state, player, opponent, mission_type, step):
        
        units = [
            mission.responsible_unit for _, mission in self.missions.items()
            if mission.mission_type == mission_type
            and mission.allow_target_change
        ]

        if len(units) == 0:
            # print("No units to assign missions")
            return
        
        target_positions = []

        if mission_type == BUILD_TILE:
            target_positions = get_important_positions(game_state, opponent, 
            self.exposed_perimeter, self.missions, player)

        
        if mission_type == GUARD_CLUSTER:
            target_positions = get_important_positions(
                game_state, 
                opponent, 
                [cell.pos for cell in self.resource_cells], 
                self.missions, player)
            
        if mission_type == EXPLORE:
            target_positions = self.exposed_perimeter

            # if step == 22:
            #     logging.warning(f"Mission is {mission_type} and targets at {[(t.x, t.y) for t in target_positions]}")
        
        # if step == 0:
        #     logging.debug(f"Mission is {mission.mission_type} and targets at {target_positions}")

        if len(target_positions) == 0:
            return
        
        target_positions.sort(key=lambda pos: (pos.x, pos.y))
        
        missions = negotiate_missions(
            self.missions,
            units,
            target_positions,
            step
        )

        self.missions = missions
        

    def get_build_actions(self, game_stats, player):
        actions = []

        for _, mission in self.missions.items():
            if mission.mission_type == BUILD_TILE and mission.target_pos is not None:
                    unit = mission.responsible_unit
                    
                    if unit.pos.equals(mission.target_pos) and unit.get_cargo_space_left() == 0 and unit.can_act() and game_stats['turns_to_night'] > 5:
                        # logging.warning("GOT HERE")
                        actions.append(unit.build_city())

        return actions
    
    def get_required_moves(self, player):
        moves = []

        for _, mission in self.missions.items():
            unit = mission.responsible_unit
            target_pos = mission.target_pos

            if not unit or not target_pos:
                continue

            if unit.can_act() and not unit.pos.equals(target_pos):
                moves.append(mission.get_moves(player))

        return moves


    def handle_explore_missions(
        self,
        game_state_info,
        resource_cells,
        player
    ):
        '''
        This function's responsibility is to prevent unit dying at night
        during long range travel to new clusters.
        If the unit does not carry enough fuel/resource to survive at night,
        we direct it to nearest resource to refill.
        '''
        actions = []
        for key in self.missions.copy():
            mission = self.missions[key]
            if mission.mission_type == EXPLORE and mission.responsible_unit is not None:

                closest_perimeter, distance = get_nearest_position(
                    mission.responsible_unit.pos,
                    self.exposed_perimeter
                )

                # This is not well thought out.
                night_turns_required = 0
                if game_state_info['is_night_time']:
                    night_turns_required = distance * 4

                turns_required = distance * 2
                if turns_required > game_state_info['turns_to_night']:
                    night_turns_required = turns_required - \
                        game_state_info['turns_to_night']

                night_fuel_required = night_turns_required * 4

                unit_fuel = 100 - mission.responsible_unit.get_cargo_space_left()

                # If the unit does not have enough fuel, we want it to go
                # to nearest resource to collect it.
                # Currently, this backfires if citytile is in front of it,
                # it can never leave the cluster because if he hits the citytile,
                # his/her carried resources are empty
                # so he/she will not have fuel to travel.
                if unit_fuel < night_fuel_required:
                    actions.append(
                        annotate.sidetext(
                            f'{mission.responsible_unit.id} You are going to die at night'
                        )
                    )
                    closest_resource_cell, distance = get_nearest_position(
                            mission.responsible_unit.pos,
                            resource_cells
                        )

                    # We do not need to go to the resource cell,
                    # just getting to the adjacent cell is enough
                    if closest_resource_cell is not None:
                        if distance == 1:
                            mission.change_target_pos(mission.responsible_unit.pos)

                        mission.change_target_pos(closest_resource_cell)
                        # This is to force non-negotiable target position.
                        # He/she needs to get resource.
                        mission.allow_target_change = False
                else:
                    mission.change_target_pos(closest_perimeter)
                    mission.allow_target_change = True

        return actions
