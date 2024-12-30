from lux.game_objects import Unit


def get_unit_by_id(id1, player) -> Unit:
    for unit in player.units:
        if unit.id == id1:
            return unit
    
