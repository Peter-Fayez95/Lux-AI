# Python Modules imports
import math, sys, time
import logging

# Lux API imports
from lux.game import Game
from lux.game_map import Cell, RESOURCE_TYPES
from lux.constants import Constants
from lux.game_constants import GAME_CONSTANTS
from lux import annotate

# My imports
from Cluster.clusterController import ClusterController
from Resources.resourceService import get_resources, get_minable_resource_cells
from Missions.Mission import Mission
from Missions.Mission import BUILD_TILE, GUARD_CLUSTER
from helperFunctions.helper_functions import get_unit_by_id


DIRECTIONS = Constants.DIRECTIONS
game_state = None

logging.basicConfig(filename="MainGame.log", level=logging.INFO)



def agent(observation, configuration):
    global game_state

    cluster_controller = None

    ### Do not edit ###
    if observation["step"] == 0:
        game_state = Game()
        game_state._initialize(observation["updates"])
        game_state._update(observation["updates"][2:])
        game_state.id = observation.player

        cluster_controller = ClusterController(width, height, game_state)
        cluster_controller.getClustersRolling(width, height, game_state)
    else:
        game_state._update(observation["updates"])
    
    actions = []

    ### AI Code goes down here! ### 
    player = game_state.players[observation.player]
    opponent = game_state.players[(observation.player + 1) % 2]
    width, height = game_state.map.width, game_state.map.height


    # Get resources
    resource_cells = get_resources(game_state)
    
    # Get resources that can be mined
    minable_resources = get_minable_resource_cells(player, resource_cells)

    # Update clusters and missions
    cluster_controller.update_clusters(game_state)
    cluster_controller.update_missions(game_state)

    # Units without home
    units_wo_clusters = cluster_controller.get_units_without_clusters(player)


    # Assign Missions to units without homes
    for unit in units_wo_clusters:
        assigned_cluster = cluster_controller.assign_mission(unit, game_state)

        if assigned_cluster is not None:
            assigned_cluster.add_unit(unit)
            current_mission = Mission(responsible_unit=unit)
            assigned_cluster.missions.append(current_mission)


    # Now, all units have missions assigned to them
    for id, cluster in cluster_controller.clusterDict.items():
        

        cluster.assign_targets_to_missions(game_state, player, opponent, BUILD_TILE)
        cluster.assign_targets_to_missions(game_state, player, opponent, GUARD_CLUSTER)

    occupied_positions = set()
    opponent_citytiles = set()
    for city in opponent.cities.values():
        for city_tile in city.citytiles:
            opponent_citytiles.add((city_tile.pos.x, city_tile.pos.y))

    occupied_positions = occupied_positions.union(opponent_citytiles)

    disabled_units_positions = set()
    for unit in player.units:
        if not unit.can_act():
            disabled_units_positions.add((unit.pos.x, unit.pos.y))
    occupied_positions = occupied_positions.union(disabled_units_positions)

    units_without_target_positions = set()

    for id, cluster in cluster_controller.clusterDict.items():
        for mission in cluster.missions:
            if mission.target_pos is None:
                unit = get_unit_by_id(mission.unit)
                units_without_target_positions.add((unit.pos.x, unit.pos.y))
    occupied_positions = occupied_positions.union(
        units_without_target_positions
    )

    units_at_target_positions = set()
    for id, cluster in cluster_controller.clusterDict.items():
        for mission in cluster.missions:
            if mission.target_pos is not None and \
                    mission.unit is not None and \
                    mission.target_pos.equals(mission.unit.pos):
                unit = get_unit_by_id(mission.unit)
                units_at_target_positions.add((unit.pos.x, unit.pos.y))
    occupied_positions = occupied_positions.union(units_at_target_positions)

    player_citytiles = set()
    for city in player.cities.values():
        for city_tile in city.citytiles:
            player_citytiles.add((city_tile.pos.x, city_tile.pos.y))

    
    occupied_positions = occupied_positions.difference(player_citytiles)



    # resource_tiles: list[Cell] = []
    # for y in range(height):
    #     for x in range(width):
    #         cell = game_state.map.get_cell(x, y)
    #         if cell.has_resource():
    #             resource_tiles.append(cell)

    # # we iterate over all our units and do something with them
    # for unit in player.units:
    #     if unit.is_worker() and unit.can_act():
    #         closest_dist = math.inf
    #         closest_resource_tile = None
    #         if unit.get_cargo_space_left() > 0:
    #             # if the unit is a worker and we have space in cargo, lets find the nearest resource tile and try to mine it
    #             for resource_tile in resource_tiles:
    #                 if resource_tile.resource.type == Constants.RESOURCE_TYPES.COAL and not player.researched_coal(): continue
    #                 if resource_tile.resource.type == Constants.RESOURCE_TYPES.URANIUM and not player.researched_uranium(): continue
    #                 dist = resource_tile.pos.distance_to(unit.pos)
    #                 if dist < closest_dist:
    #                     closest_dist = dist
    #                     closest_resource_tile = resource_tile
    #             if closest_resource_tile is not None:
    #                 actions.append(unit.move(unit.pos.direction_to(closest_resource_tile.pos)))
    #         else:
    #             # if unit is a worker and there is no cargo space left, and we have cities, lets return to them
    #             if len(player.cities) > 0:
    #                 closest_dist = math.inf
    #                 closest_city_tile = None
    #                 for k, city in player.cities.items():
    #                     for city_tile in city.citytiles:
    #                         dist = city_tile.pos.distance_to(unit.pos)
    #                         if dist < closest_dist:
    #                             closest_dist = dist
    #                             closest_city_tile = city_tile
    #                 if closest_city_tile is not None:
    #                     move_dir = unit.pos.direction_to(closest_city_tile.pos)
    #                     actions.append(unit.move(move_dir))


    # you can add debug annotations using the functions in the annotate object
    # actions.append(annotate.circle(0, 0))
    
    
    
    # logging.info(f"Number of Clusters: {len(controller.clusterDict)}")
    # for clusterid, cluster in controller.clusterDict.items():
    #     logging.info(f"Cluster #{clusterid} Properties:")
    #     logging.info(f"Cluster Resource Type: {cluster.resource_type}")
    #     logging.info(f"Cluster Resource Cells: {[cell.pos.__str__() for cell in cluster.resource_cells]}")
    #     logging.info(f"Cluster Perimeter: {cluster.get_perimeter(game_state)}")
    #     logging.info(f"Cluster Fuel: {cluster.get_total_fuel()}")
    #     logging.info(f"Cluster Centroid: {cluster.get_centroid()}")
    #     logging.info(f"{'-' * 30}")

    # time.sleep(3)

    return actions
