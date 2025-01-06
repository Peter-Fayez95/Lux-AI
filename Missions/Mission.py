from Units.unitsService import get_unit_by_id
from Map.mapService import get_directions
from lux.game_map import Position

from typing import Union
from typeguard import typechecked


@typechecked
class Mission:
    """
    Class for handling missions

    mission_type            int             Type of mission
    target_pos              Position        Target Position
    responsible_unit        str             Responsible unit id
    """

    def __init__(
        self,
        responsible_unit: str = None,
        mission_type: int = None,
        target_pos: Union[Position, None] = None,
    ) -> None:
        self.mission_type = mission_type
        self.target_pos = target_pos
        self.responsible_unit = responsible_unit
        self.allow_target_change = True

    def change_responsible_unit(self, responsible_unit: str):
        self.responsible_unit = responsible_unit

    def change_target_pos(self, target_pos: Position):
        self.target_pos = target_pos

    def get_moves(self, player):
        unit = get_unit_by_id(self.responsible_unit, player)
        target_pos = self.target_pos

        directions = get_directions(unit.pos, target_pos)

        movements = []
        for direction in directions:
            next_pos = unit.pos.translate(direction, 1)
            movements.append({"direction": direction, "next_pos": next_pos})

        return {
            "unit_id": unit.id,
            "unit": unit,
            "movements": movements,
            "approved": False,
            "mission": self,
        }
