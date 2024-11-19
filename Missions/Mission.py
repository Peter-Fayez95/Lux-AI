
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