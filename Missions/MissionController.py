from Missions.Mission import Mission
from constants import BUILD_TILE

class MissionController:
    def remove_finished_tile_missions(missions, game_state):
        '''
        Remove all finished BUILD_TILE missions
        '''
        for mission in missions.copy():
            if mission.mission_type == BUILD_TILE:
                target_pos = game_state.get_cell_by_pos(mission.target_pos)
                
                if target_pos.citytile:
                    del missions[missions.index(mission)]
        

    def remove_finished_guard_missions(missions):
        '''
        Remove all finished GUARD_CLUSTER missions
        '''
        for mission in missions.copy():
            if mission.mission_type == BUILD_TILE:
                if mission.target_pos == mission.responsible_unit.pos:
                    del missions[missions.index(mission)]

    def remove_missions_with_no_units(missions, units):
        '''
        Remove all missions with no responsible units
        '''
        for mission in missions.copy():
            if mission.responsible_unit.id not in units:
                del missions[missions.index(mission)]