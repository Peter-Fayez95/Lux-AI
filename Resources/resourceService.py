from typing import List
from lux.game_map import Cell, Position, RESOURCE_TYPES


def get_resources(game_state):
    '''
    Get all resource cells in the game map.
    '''
    resource_cells = []
    width, height = game_state.map_width, game_state.map_height
    for y in range(height):
        for x in range(width):
            cell = game_state.map.get_cell(x, y)
            if cell.has_resource():
                resource_cells.append(cell)
    return resource_cells

def get_minable_resource_cells(
    player, 
    resource_cells: List[Cell]
    ) -> List[Cell]:
    '''
    Get resource cells that can be mined by the player.
    '''
    minable_resource_types = [RESOURCE_TYPES.WOOD]
    if player.researched_coal():
        minable_resource_types.append(RESOURCE_TYPES.COAL)
    if player.researched_uranium():
        minable_resource_types.append(RESOURCE_TYPES.URANIUM)

    minable_resource_cells = [
        resource_cell for resource_cell in resource_cells
        if resource_cell.resource.type in minable_resource_types
    ]
    return minable_resource_cells

def get_resources_from_cells(gamestate, cells: List[Cell]):
    '''
    Given the Cells list `cells`
    return the resource cells from this list
    '''
    resource_cells = []
    for cell in cells:
        if cell.has_resource():
            resource_cells.append(cell)
    
    return resource_cells