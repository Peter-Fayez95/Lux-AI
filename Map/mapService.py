from lux.game_map import Cell, Position
from lux.constants import Constants
from copy import deepcopy
from typing import List
import math

from Units.unitsService import get_unit_by_id


DIRECTIONS = Constants.DIRECTIONS


def inside_map(x, y, width, height):
    """
    Check if the cell(x, y) is inside the map
    """
    return (0 <= x < width) and (0 <= y < height)


def inside_map(pos: Position, width, height):
    return (0 <= pos.x < width) and (0 <= pos.y < height)


def get_cell_neighbours_four(cell: Cell, gamestate):
    """
    Get Cells Four Neighbours
    """
    neighbours = []
    for dir in [DIRECTIONS.NORTH, DIRECTIONS.EAST, DIRECTIONS.SOUTH, DIRECTIONS.WEST]:
        pos = deepcopy(cell.pos)
        pos = pos.translate(dir, 1)

        if inside_map(pos, gamestate.map.width, gamestate.map.height):
            translated_cell = gamestate.map.get_cell(pos.x, pos.y)

            neighbours.append(translated_cell)
    return neighbours


def get_cell_neighbours_eight(cell: Cell, gamestate):
    """
    Get Cells Eight Neighbours
    """
    neighbours = get_cell_neighbours_four(cell, gamestate)

    dir1 = 0
    dir2 = 1

    # Get the other four neighbours
    for i in range(4):
        directions = [
            DIRECTIONS.NORTH,
            DIRECTIONS.EAST,
            DIRECTIONS.SOUTH,
            DIRECTIONS.WEST,
        ]
        pos = deepcopy(cell.pos)
        pos = pos.translate(directions[dir1], 1)
        pos = pos.translate(directions[dir2], 1)

        dir1 = (dir1 + 1) % len(directions)
        dir2 = (dir2 + 1) % len(directions)

        if inside_map(pos, gamestate.map.width, gamestate.map.height):

            translated_cell = gamestate.map.get_cell(pos.x, pos.y)

            neighbours.append(translated_cell)

    return neighbours


def get_nearest_position(C: Position, cells: List[Position]):
    """
    Given a cell `C`
    Return the smallest distance and cell to it from a list of cells
    """
    nearest_position = None
    smallest_distance = math.inf

    for cell in cells:
        if type(cell) == tuple:
            cell = Position(cell[0], cell[1])
        elif type(cell) == Cell:
            cell = cell.pos
        current_distance = C.distance_to(cell)

        if current_distance < smallest_distance:
            smallest_distance = current_distance
            nearest_position = cell

    return nearest_position, smallest_distance


def get_perimeter(cells, game_state):
    distinct_cells = set()
    for cell in cells:
        for neighbour in get_cell_neighbours_four(cell, game_state):

            if not neighbour.has_resource():
                distinct_cells.add((neighbour.pos.x, neighbour.pos.y))

    return distinct_cells


def get_directions(src, dest):
    directions = []
    if dest.y - src.y < 0:
        directions.append(DIRECTIONS.NORTH)
    if dest.y - src.y > 0:
        directions.append(DIRECTIONS.SOUTH)
    if dest.x - src.x > 0:
        directions.append(DIRECTIONS.EAST)
    if dest.x - src.x < 0:
        directions.append(DIRECTIONS.WEST)
    return directions


def get_occupied_positions(player, opponent, cluster_controller):
    # occupied_positions = opponent tiles + disabled units +
    #   units without target + units at target - our citytiles
    occupied_positions = set()

    # Add opponent tiles to occupied positions
    for city in opponent.cities.values():
        for city_tile in city.citytiles:
            occupied_positions.add((city_tile.pos.x, city_tile.pos.y))

    # Add disabled units to occupied positions
    for unit in player.units:
        if not unit.can_act():
            occupied_positions.add((unit.pos.x, unit.pos.y))

    # Add units without target positions to occupied positions
    for cluster in cluster_controller.clusterDict.values():
        for mission in cluster.missions:
            if mission.target_pos is None:
                unit = get_unit_by_id(mission.responsible_unit, player)

                occupied_positions.add((unit.pos.x, unit.pos.y))

    # Add units at target positions to occupied positions
    for cluster in cluster_controller.clusterDict.values():
        for mission in cluster.missions:
            if mission.target_pos is not None and mission.responsible_unit is not None:
                unit = get_unit_by_id(mission.responsible_unit, player)
                if mission.target_pos.equals(unit.pos):
                    occupied_positions.add((unit.pos.x, unit.pos.y))

    player_citytiles = set()
    for city in player.cities.values():
        for city_tile in city.citytiles:
            player_citytiles.add((city_tile.pos.x, city_tile.pos.y))

    occupied_positions = occupied_positions.difference(player_citytiles)

    return occupied_positions
