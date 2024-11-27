from helperFunctions import get_directions


class Mission:
    '''
    Class for handling missions

    mission_type            str             Type of mission
    target_pos              Position        Target Position
    responsible_unit_id     str             Responsible unit id
    '''
    def __init__(self, responsible_unit = None, type = None, target_pos=None):
        self.mission_type = type
        self.target_pos = target_pos
        self.responsible_unit = responsible_unit
    
    def change_responsible_unit(self, responsible_unit):
        self.responsible_unit = responsible_unit
    
    def change_target_pos(self, target_pos):
        self.target_pos = target_pos

    def get_moves(self):
        unit = self.unit
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