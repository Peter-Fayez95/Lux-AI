from Units.unitsService import get_unit_by_id
from Map.mapService import get_directions
from lux.game_map import Position

class Mission:
    '''
    Class for handling missions

    mission_type            str             Type of mission
    target_pos              Position        Target Position
    responsible_unit        str             Responsible unit id
    '''
    def __init__(self, responsible_unit=None, mission_type=None, target_pos=None):
        self.mission_type = mission_type
        
        if target_pos is not None and isinstance(target_pos, tuple):
            target_pos = Position(target_pos[0], target_pos[1])
        
        self.target_pos = target_pos
        self.responsible_unit = responsible_unit
        self.allow_target_change = True
        
    
    def change_responsible_unit(self, responsible_unit):
        self.responsible_unit = responsible_unit
    
    def change_target_pos(self, target_pos):
        if type(target_pos) is tuple:
            target_pos = Position(target_pos[0], target_pos[1])
        self.target_pos = target_pos

    def get_moves(self, player):
        unit = get_unit_by_id(self.responsible_unit, player)
        target_pos = self.target_pos

        directions = get_directions(
            unit.pos, target_pos
        )

        movements = []
        for direction in directions:
            next_pos = unit.pos.translate(direction, 1)
            movements.append({
                'direction': direction,
                'next_pos': next_pos
            })

        return {
            'unit_id': unit.id,
            'unit': unit,
            'movements': movements,
            'approved': False,
            'mission': self
        }