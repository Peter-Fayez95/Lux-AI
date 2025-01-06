#
#
# This module contains helper functions that can be used over all classes
#
#
from lux.game_constants import GAME_CONSTANTS

import math
from functools import cmp_to_key

from lux.game_map import Position
from lux.constants import Constants

from Map.mapService import get_perimeter
from Units.unitsService import get_unit_by_id
from Enemy.enemyService import get_enemy_coverage

DIRECTIONS = Constants.DIRECTIONS

# TODO: Add unittests for this module


def get_build_position_score(game_state, opponent, pos, center):
    if isinstance(center, tuple):
        center = Position(center[0], center[1])

    if isinstance(pos, tuple):
        pos = Position(pos[0], pos[1])

    travel_distance = center.distance_to(pos)
    travel_distance_score = 100 / ((travel_distance**2) + 1)

    opponent_distances = []
    for unit in opponent.units:
        distance = pos.distance_to(unit.pos)
        opponent_distances.append(distance)

    opponent_distance_score = (10 * len(opponent.units)) / (sum(opponent_distances) + 1)

    perimeter = get_perimeter([game_state.map.get_cell_by_pos(pos)], game_state)

    perimeter_score = 0
    for p in perimeter:
        pos = Position(p[0], p[1])
        cell = game_state.map.get_cell_by_pos(pos)
        if cell.citytile is not None:
            perimeter_score += 2

    final_score = perimeter_score + opponent_distance_score + travel_distance_score

    return final_score


def get_important_positions(game_state, opponent, available_targets, missions, player):

    sum_x = 0
    sum_y = 0

    for mission in missions:
        if mission.responsible_unit is None:
            continue

        unit = get_unit_by_id(mission.responsible_unit, player)
        sum_x += unit.pos.x
        sum_y += unit.pos.y

    mean_x = sum_x / len(missions)
    mean_y = sum_y / len(missions)

    center = Position(mean_x, mean_y)

    def compare(pos1, pos2):
        return pos2[0] - pos1[0]

    pos_score_vector = []

    for pos in available_targets:
        score = get_build_position_score(game_state, opponent, pos, center)

        pos_score_vector.append([score, pos])

    pos_score_vector.sort(key=cmp_to_key(compare))

    return [pos_score[1] for pos_score in pos_score_vector][: len(missions)]


def negotiate_actions(occupied_positions, requested_movements):
    """
    This is just a simple heuristics.
    We prioritize unit that has only one direction to go.
    Currently, the unit does not have intelligence to make it way around
    and obstacle. If there is an obstacle, he/she simple waits till
    the obstacle is gone. More research is needed.
    """

    # TO-DO make it more efficient
    # SORT UNIT BY PRIORTIY HEURISTICS
    actions = []

    # unmovable_units or obstacles
    for requested_movement in requested_movements:
        for movement in requested_movement["movements"]:
            if (
                movement["next_pos"].x,
                movement["next_pos"].y,
            ) not in occupied_positions:
                break

            occupied_positions.add(
                (requested_movement["unit"].pos.x, requested_movement["unit"].pos.y)
            )
            requested_movement["approved"] = False

    for requested_movement in requested_movements:
        if len(requested_movement["movements"]) == 1:
            movement = requested_movement["movements"][0]
            if (
                movement["next_pos"].x,
                movement["next_pos"].y,
            ) not in occupied_positions:
                actions.append(requested_movement["unit"].move(movement["direction"]))
                occupied_positions.add((movement["next_pos"].x, movement["next_pos"].y))
                requested_movement["approved"] = True
            else:
                occupied_positions.add(
                    (requested_movement["unit"].pos.x, requested_movement["unit"].pos.y)
                )

    for requested_movement in requested_movements:
        if len(requested_movement["movements"]) > 1:
            movements = requested_movement["movements"]
            for movement in movements:
                if (
                    movement["next_pos"].x,
                    movement["next_pos"].y,
                ) not in occupied_positions:
                    actions.append(
                        requested_movement["unit"].move(movement["direction"])
                    )
                    occupied_positions.add(
                        (movement["next_pos"].x, movement["next_pos"].y)
                    )
                    requested_movement["approved"] = True
                    break

        if not requested_movement["approved"]:
            occupied_positions.add(
                (requested_movement["unit"].pos.x, requested_movement["unit"].pos.y)
            )

    return actions


def get_closest_cluster_by_centroid(citytile, cluster_dict):
    """
    We sort the clusters by the distance to the cluster center
    """
    closest_distance = math.inf
    closest_cluster = None

    for id, cluster in cluster_dict.items():
        distance = citytile.pos.distance_to(cluster.get_centroid())
        if distance < closest_distance:
            closest_distance = distance
            closest_cluster = id

    return closest_cluster, closest_distance


def get_citytile_score(cluster, game_state, player_id, opponent, opponent_id):
    """
    A simple mathematical model to calculate if a citytile should build a worker.
    """
    # directly proportional
    resource_cell_score = len(cluster.resource_cells)
    fuel_score = cluster.get_total_fuel() / 100

    perimeter = get_perimeter(cluster.resource_cells, game_state)
    perimeter_score = len(perimeter)

    opponent_citytiles, opponent_units = get_enemy_coverage(
        [game_state.map.get_cell_by_pos(Position(pos[0], pos[1])) for pos in perimeter],
        opponent,
        opponent_id,
    )
    opponent_workers_score = len(opponent_units) + 1
    opponent_citytiles_score = len(opponent_citytiles) + 1

    # inversely proportional
    player_citytiles = []
    for p in perimeter:
        cell = game_state.map.get_cell_by_pos(Position(p[0], p[1]))
        if cell.citytile is not None:
            if cell.citytile.team == player_id:
                player_citytiles.append(cell.citytile)

    player_workers_score = 10 * len(cluster.units) + 1
    player_citytiles_score = len(player_citytiles) + 1

    no_player_unit_bonus = 10 if len(cluster.units) == 0 else 1

    numerator = (
        resource_cell_score
        * fuel_score
        * perimeter_score
        * no_player_unit_bonus
        * opponent_workers_score
        * opponent_citytiles_score
    )

    denominator = player_workers_score * player_citytiles_score

    citytile_score = numerator / (denominator + 1.1)

    return citytile_score


def get_city_actions(
    game_state, game_state_info, player, clusters_dict, player_id, opponent, opponent_id
):
    """
    Build worker if possible.
    If two tiles need to build, take the one with the highest score.
    """
    actions = []
    units_capacity = sum([len(x.citytiles) for x in player.cities.values()])
    units_count = len(player.units)

    actionable_citytiles = []
    for city in player.cities.values():
        for citytile in city.citytiles:
            if citytile.can_act():
                actionable_citytiles.append(citytile)

    citytiles_to_be_sorted = []
    for citytile in actionable_citytiles:
        # We do not keep track of which cluster a citytile belongs to.
        # So, we need to find it here.
        closest_cluster, _ = get_closest_cluster_by_centroid(citytile, clusters_dict)
        citytile_score = 0

        if closest_cluster is not None:
            closest_cluster = clusters_dict[closest_cluster]
            citytile_score = get_citytile_score(
                closest_cluster, game_state, player_id, opponent, opponent_id
            )

        citytiles_to_be_sorted.append({"citytile": citytile, "score": citytile_score})

    def compare(citytile1, citytile2):
        return citytile2["score"] - citytile1["score"]

    sorted_citytiles = sorted(citytiles_to_be_sorted, key=cmp_to_key(compare))

    research_count = 0
    for citytile in sorted_citytiles:
        if (
            units_count < units_capacity and game_state_info["turns_to_night"] > 4
        ) or player.research_points + research_count >= 200:
            actions.append(citytile["citytile"].build_worker())
            units_count += 1
        else:
            if not player.researched_uranium():
                actions.append(citytile["citytile"].research())
            research_count += 1

    return actions


def update_game_stats(turn):
    MAX_DAYS = GAME_CONSTANTS["PARAMETERS"]["MAX_DAYS"]
    DAY_LENGTH = GAME_CONSTANTS["PARAMETERS"]["DAY_LENGTH"]
    NIGHT_LENGTH = GAME_CONSTANTS["PARAMETERS"]["NIGHT_LENGTH"]
    FULL_LENTH = DAY_LENGTH + NIGHT_LENGTH

    all_night_turns_lef = ((MAX_DAYS - 1 - turn) // FULL_LENTH + 1) * NIGHT_LENGTH

    turns_to_night = (DAY_LENGTH - turn) % FULL_LENTH
    turns_to_night = 0 if turns_to_night > 30 else turns_to_night

    turns_to_dawn = FULL_LENTH - turn % FULL_LENTH
    turns_to_dawn = 0 if turns_to_dawn > 10 else turns_to_dawn

    is_day_time = turns_to_dawn == 0
    is_night_time = turns_to_night == 0

    if is_night_time:
        all_night_turns_lef -= 10 - turns_to_dawn

    return {
        "all_night_turns_left": all_night_turns_lef,
        "turns_to_night": turns_to_night,
        "turns_to_dawn": turns_to_dawn,
        "is_day_time": is_day_time,
        "is_night_time": is_night_time,
    }
