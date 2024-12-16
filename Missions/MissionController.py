
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
import logging

from lux.game_map import Position
from lux import annotate

from Missions.Mission import Mission
from Missions.constants import BUILD_TILE, EXPLORE, GUARD_CLUSTER
from helperFunctions.helper_functions import get_unit_by_id

logging.basicConfig(filename="Game.log", level=logging.INFO, force=True)



def negotiate_missions(missions, units, targets, step):
    # print("Negotiating missions")
    unit_positions = [(unit.pos.x, unit.pos.y) for unit in units]
    
    if isinstance(targets[0], tuple):
        targets = [Position(target[0], target[1]) for target in targets]

    target_positions = [(target.x, target.y) for target in targets]

    def distance_to(pos1, pos2):
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

    distance_matrix = cdist(
        unit_positions,
        target_positions,
        distance_to
    )

    # if step == 23:
        # logging.info(f"Units: {[unit.id for unit in units]}")
        # logging.info(f"Targets: {target_positions}")

    row_ind, col_ind = linear_sum_assignment(distance_matrix)
    for i in range(len(row_ind)):
        key = units[row_ind[i]].id
        target = target_positions[col_ind[i]]
        missions[key].change_target_pos(Position(target[0], target[1]))

    return missions



def get_annotations(missions, player):
    annotations = []

    for unit, mission in missions.items():
        if mission.target_pos is None or mission.responsible_unit is None:
            continue

        unit = mission.responsible_unit

        if mission.mission_type == GUARD_CLUSTER and mission.target_pos is not None:
            annotations.append(
                annotate.circle(
                    mission.target_pos.x,
                    mission.target_pos.y,
                )
            )
            annotations.append(
                annotate.line(
                    unit.pos.x,
                    unit.pos.y,
                    mission.target_pos.x,
                    mission.target_pos.y,
                )
            )

        
        if mission.mission_type == BUILD_TILE and mission.target_pos is not None:
            annotations.append(
                annotate.x(
                    mission.target_pos.x,
                    mission.target_pos.y,
                )
            )
            annotations.append(
                annotate.line(
                    unit.pos.x,
                    unit.pos.y,
                    mission.target_pos.x,
                    mission.target_pos.y,
                )
            )

        if mission.mission_type == EXPLORE and mission.target_pos is not None:

            annotations.append(
                annotate.line(
                    unit.pos.x,
                    unit.pos.y,
                    mission.target_pos.x,
                    mission.target_pos.y,
                )
            )
            annotations.append(
                annotate.x(
                    mission.target_pos.x,
                    mission.target_pos.y,
                )
            )
            annotations.append(
                annotate.circle(
                    mission.target_pos.x,
                    mission.target_pos.y,
                )
            )
    return annotations
            