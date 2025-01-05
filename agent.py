# Python Modules imports
import logging

# Lux API imports
from lux.game import Game

# My imports
from Cluster.clusterController import ClusterController
from Resources.resourceService import get_resources, get_minable_resource_cells
from Missions.Mission import Mission
from Missions.constants import BUILD_TILE, GUARD_CLUSTER, EXPLORE
from helperFunctions.helper_functions import (
    negotiate_actions,
    update_game_stats,
    get_city_actions,
)
from Units.unitsService import get_unit_by_id


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
    game_stats = update_game_stats(observation["step"])
    my_id = observation.player
    opponent_id = (observation.player + 1) % 2

    ### AI Code goes down here! ###
    player = game_state.players[observation.player]
    opponent = game_state.players[(observation.player + 1) % 2]

    # Get resources and minable resources
    resource_cells = get_resources(game_state)
    minable_resources = get_minable_resource_cells(player, resource_cells)

    # Update Clusters
    cluster_controller.update_clusters(game_state, player)
    cluster_controller.update_missions(game_state, player)

    # Units without home cluster
    units_wo_clusters = cluster_controller.get_units_without_clusters(player)

    # Assign Missions to units without homes
    for unit in units_wo_clusters:
        assigned_cluster = cluster_controller.assign_worker(
            unit, game_state, player, my_id, opponent
        )

        if assigned_cluster is not None:
            assigned_cluster.add_unit(unit.id)
            current_mission = Mission(responsible_unit=unit.id, mission_type=EXPLORE)
            assigned_cluster.missions.append(current_mission)

    # After assigning missions to units without homes, update the list
    units_wo_clusters = cluster_controller.get_units_without_clusters(player)

    # Now, all units have missions assigned to them
    # Instruct Clusters to assign targets to missions
    for cluster in cluster_controller.clusterDict.values():
        cluster.assign_targets_to_missions(
            game_state, player, opponent, BUILD_TILE, observation["step"]
        )
        cluster.assign_targets_to_missions(
            game_state, player, opponent, GUARD_CLUSTER, observation["step"]
        )

        cluster.handle_explore_missions(game_stats, minable_resources, player)
        cluster.assign_targets_to_missions(
            game_state, player, opponent, EXPLORE, observation["step"]
        )

    # occupied_positions = opponent tiles + disabled units +
    #   units without target + units at target - our citytiles
    occupied_positions = set()

    # Add opponent tiles to occupied positions
    for city in opponent.cities.values():
        for city_tile in city.citytiles:
            occupied_positions.add((city_tile.pos.x, city_tile.pos.y))

    # Add disabled units to occupied positions
    for unit in player.units:
        if not unit.can_act():
            occupied_positions.add((unit.pos.x, unit.pos.y))

    # Add units without target positions to occupied positions
    for cluster in cluster_controller.clusterDict.values():
        for mission in cluster.missions:
            if mission.target_pos is None:
                unit = get_unit_by_id(mission.responsible_unit, player)

                occupied_positions.add((unit.pos.x, unit.pos.y))

    # Add units at target positions to occupied positions
    for cluster in cluster_controller.clusterDict.values():
        for mission in cluster.missions:
            if mission.target_pos is not None and mission.responsible_unit is not None:
                unit = get_unit_by_id(mission.responsible_unit, player)
                if mission.target_pos.equals(unit.pos):
                    occupied_positions.add((unit.pos.x, unit.pos.y))

    player_citytiles = set()
    for city in player.cities.values():
        for city_tile in city.citytiles:
            player_citytiles.add((city_tile.pos.x, city_tile.pos.y))

    occupied_positions = occupied_positions.difference(player_citytiles)

    for cluster in cluster_controller.clusterDict.values():
        if len(cluster.missions) == 0:
            continue

        actions.extend(cluster.get_build_actions(game_stats, player))

    # Getting the required movements for all clusters
    required_moves = list()
    for cluster in cluster_controller.clusterDict.values():
        moves = cluster.get_required_moves(player)

        required_moves.extend(moves)

    # Add the valid actions (those who have occupied positions are not valid)
    actions.extend(negotiate_actions(occupied_positions, required_moves))

    actions.extend(
        get_city_actions(
            game_state,
            game_stats,
            player,
            cluster_controller.clusterDict,
            my_id,
            opponent,
            opponent_id,
        )
    )
    return actions
