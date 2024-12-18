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
from Missions.constants import BUILD_TILE, GUARD_CLUSTER, EXPLORE
from helperFunctions.helper_functions import get_unit_by_id, get_directions, \
        negotiate_actions, update_game_stats, get_city_actions, get_opponent_tiles



logging.basicConfig(filename="Game.log", level=logging.INFO, force=True)



def agent(observation, configuration):
    global game_state, game_stats
    global cluster_controller
    

    ### Do not edit ###
    if observation["step"] == 0:
        game_state = Game()
        game_state._initialize(observation["updates"])
        game_state._update(observation["updates"][2:])
        game_state.id = observation.player
        width, height = game_state.map.width, game_state.map.height

        cluster_controller = ClusterController(width, height, game_state)
        cluster_controller.getClustersRolling(width, height, game_state)
    else:
        game_state._update(observation["updates"])
    

    actions = []
    game_stats = update_game_stats(observation['step'])
    my_id = observation.player
    opponent_id = (observation.player + 1) % 2

    ### AI Code goes down here! ### 
    player = game_state.players[observation.player]
    opponent = game_state.players[(observation.player + 1) % 2]


    # Get resources
    resource_cells = get_resources(game_state)

    # logging.info(f"Number of Resource Cells: {len(resource_cells)}")
    
    opponent_citytiles = get_opponent_tiles(opponent)

    # Get resources that can be mined
    minable_resources = get_minable_resource_cells(player, resource_cells)
    # logging.info(f"Number of Minable Resource Cells: {len(minable_resources)}")

    cluster_controller.update_clusters(game_state, player)
    cluster_controller.update_missions(game_state, player)

    # Units without home
    units_wo_clusters = cluster_controller.get_units_without_clusters(player)
    # print("DDDDD", units_wo_clusters)


    # if observation["step"] == 0:
    #     print(f"Number of Units without Clusters: {len(units_wo_clusters)}")

    # Assign Missions to units without homes
    for unit in units_wo_clusters:
        assigned_cluster = cluster_controller.assign_worker(unit, game_state, player, my_id, opponent)

        if assigned_cluster is not None:
            # logging.warning(f"Unit {unit.id} assigned to Cluster at {assigned_cluster.get_centroid().x} {assigned_cluster.get_centroid().y}")
            assigned_cluster.add_unit(unit.id)
            current_mission = Mission(responsible_unit=unit.id, mission_type=EXPLORE)
            assigned_cluster.missions.append(current_mission)

    units_wo_clusters = cluster_controller.get_units_without_clusters(player)
    # print("Number of Units without Clusters: ", len(units_wo_clusters))
    
    # ghost_units = []

    for cluster in cluster_controller.clusterDict.values():
        for mission in cluster.missions:
            unit = get_unit_by_id(mission.responsible_unit, player)
            mission.change_responsible_unit(unit.id)

    # for cluster in cluster_controller.clusterDict.values():
    #     for mission in cluster.missions:
    #         if mission.responsible_unit is None:
    #             logging.warning(f"Mission {mission} has no responsible unit")

    # for unit in player.units:
    #     logging.info(f"MY Unit {unit.id}")

    # for unit in ghost_units:
    #     logging.warning(f"{unit} is a ghost unit")
    
    # print("------------------")

    # Now, all units have missions assigned to them
    for cluster in cluster_controller.clusterDict.values():
        # logging.warning(f"Cluster {cluster} has {len(cluster.missions)} missions")

        cluster.assign_targets_to_missions(game_state, player, opponent, BUILD_TILE, observation['step'])
        cluster.assign_targets_to_missions(game_state, player, opponent, GUARD_CLUSTER, observation['step'])

        # logging.warning(f"zzz1")
        cluster.handle_explore_missions(game_stats, minable_resources, player)
        cluster.assign_targets_to_missions(game_state, player, opponent, EXPLORE, observation['step'])

        # if cluster.missions != []:
            # print(cluster.missions[0].target_pos, cluster.missions[0].mission_type)



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

    for cluster in cluster_controller.clusterDict.values():
        for mission in cluster.missions:
            if mission.target_pos is None:
                unit = get_unit_by_id(mission.responsible_unit, player)
                
                # This condition is not supposed to be here
                # Should look into this
                # if unit is not None:
                units_without_target_positions.add((unit.pos.x, unit.pos.y))
    
    
    occupied_positions = occupied_positions.union(
        units_without_target_positions
    )

    units_at_target_positions = set()
    for cluster in cluster_controller.clusterDict.values():
        for mission in cluster.missions:
            if mission.target_pos is not None and mission.responsible_unit is not None:
                unit = get_unit_by_id(mission.responsible_unit, player)
                if mission.target_pos.equals(unit.pos):
                    units_at_target_positions.add((unit.pos.x, unit.pos.y))
    occupied_positions = occupied_positions.union(units_at_target_positions)

    player_citytiles = set()
    for city in player.cities.values():
        for city_tile in city.citytiles:
            player_citytiles.add((city_tile.pos.x, city_tile.pos.y))

    
    occupied_positions = occupied_positions.difference(player_citytiles)




    # GET ACTIONS
    # ____________

    required_moves = list()
    for cluster in cluster_controller.clusterDict.values():
        if len(cluster.missions) == 0:
            continue
        
        # print(f"This cluster has {len(cluster.missions)} missions")
        actions.extend(cluster.get_build_actions(game_stats, player))
        
    

    for cluster in cluster_controller.clusterDict.values():
        moves = cluster.get_required_moves(player)
        
        required_moves.extend(moves)

    # print(required_moves)

    
    # Add the valid actions (those who have occupied positions are not valid)
    actions.extend(negotiate_actions(occupied_positions, required_moves))

    actions.extend(get_city_actions(game_state,
                                    game_stats,
                                    player,
                                    cluster_controller.clusterDict, 
                                    my_id,
                                    opponent,
                                    opponent_id))


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

    # print(actions)
    logging.debug("------------------------------")

    return actions
