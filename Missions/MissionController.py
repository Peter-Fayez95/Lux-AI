
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist

from lux.game_map import Position


from Missions.Mission import Mission
from Missions.constants import BUILD_TILE, EXPLORE, GUARD_CLUSTER
from helperFunctions.helper_functions import get_unit_by_id


def remove_finished_tile_missions(missions, game_state):
    '''
    Remove all finished BUILD_TILE missions
    '''
    for mission in missions.copy():
        if mission.target_pos is None:
            continue
        
        if mission.mission_type == BUILD_TILE:
            target_pos = game_state.map.get_cell_by_pos(mission.target_pos)
            
            if target_pos.citytile:
                del missions[missions.index(mission)]
    
def remove_finished_explore_missions(missions, player):
    '''
    Remove all finished EXPLORE missions
    '''
    for mission in missions.copy():
        if mission.target_pos is None:
            continue
        
        if mission.mission_type == EXPLORE:
            unit = get_unit_by_id(mission.responsible_unit, player)
            if unit.pos.equals(mission.target_pos) and mission.allow_target_change:
                del missions[missions.index(mission)]

def remove_finished_guard_missions(missions, player):
    '''
    Remove all finished GUARD_CLUSTER missions
    '''
    for mission in missions.copy():
        if mission.target_pos is None:
            continue

        if mission.mission_type == GUARD_CLUSTER:
            unit = get_unit_by_id(mission.responsible_unit, player)
            if mission.target_pos == unit.pos:
                del missions[missions.index(mission)]

def remove_missions_with_no_units(missions, units):
    '''
    Remove all missions with no responsible units
    '''
    for mission in missions.copy():
        if mission.responsible_unit is not None and mission.responsible_unit not in units:
            del missions[missions.index(mission)]


def negotiate_missions(missions, units, targets):
    unit_positions = [(unit.pos.x, unit.pos.y) for unit in units]

    targets_to_positions = targets
    if isinstance(targets[0], tuple):
        targets_to_positions = [Position(t[0], t[1]) for t in targets]

    target_positions = [(target.x, target.y) for target in targets_to_positions]

    def distance_to(pos1, pos2):
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

    distance_matrix = cdist(
        unit_positions,
        target_positions,
        distance_to
    )

    row_ind, col_ind = linear_sum_assignment(distance_matrix)
    for i in range(len(row_ind)):
        key = units[row_ind[i]].id
        target = target_positions[col_ind[i]]
        for mission in missions:
            if mission.responsible_unit == key:
                mission.change_target_pos(Position(target[0], target[1]))

    return missions