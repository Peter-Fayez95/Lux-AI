
class Mission:
    '''
    Class for handling missions

    mission_type            str             Type of mission
    target_pos              Position        Target Position
    responsible_unit_id     int             Responsible unit id
    '''
    def __init__(self, responsible_unit, type, target_pos):
        self.mission_type = type
        self.target_pos = target_pos
        self.responsible_unit = responsible_unit
    
    def change_responsible_unit(self, responsible_unit):
        self.responsible_unit = responsible_unit
    
    def change_target_pos(self, target_pos):
        self.target_pos = target_pos