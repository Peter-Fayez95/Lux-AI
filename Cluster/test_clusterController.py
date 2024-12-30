from lux.game_map import Position, Resource
from Cluster.clusterController import ClusterController


# TODO: Refactor Game API for these classes
class Cell:
    def __init__(self, x, y, resource: Resource = None):
        self.resource = resource
        self.pos = Position(x, y)

    def has_resource(self):
        return self.resource.amount > 0


class Map:
    def __init__(self, map, width, height):
        self.map = map
        self.width = width
        self.height = height

    def get_cell(self, x, y):
        return self.map[x][y]


class GameState:
    def __init__(self, map):
        self.map = map


class TestClass:
    """
    Maps are encoded from 0 to 9
    0: No resources in this cell
    9: This cell has resource amount of 9
    """

    def stringToMap(width, height, map_string):
        """
        Convert the map_string to an actual game map
        """
        cells = [
            [
                Cell(resource=Resource("uranium", int(map_string[x][y])), x=x, y=y)
                for y in range(height)
            ]
            for x in range(width)
        ]
        return cells

    def test_one(self):
        map_string = ["000000", "011110", "011110", "000000"]

        width = 4
        height = 6

        # Variables to be compared in Unit Test
        cluster = [[[1, 1], [2, 1], [2, 2], [2, 3], [2, 4], [1, 4], [1, 3], [1, 2]]]
        perimeter = [
            [0, 1],
            [0, 2],
            [0, 3],
            [0, 4],
            [1, 0],
            [1, 5],
            [2, 0],
            [2, 5],
            [3, 1],
            [3, 2],
            [3, 3],
            [3, 4],
        ]

        mapp = Map(
            [
                [Cell(resource=Resource("uranium", 0), x=x, y=y) for y in range(height)]
                for x in range(width)
            ],
            width,
            height,
        )

        for i in range(1, width - 1):
            for j in range(1, height - 1):
                mapp.map[i][j] = Cell(resource=Resource("uranium", 1), x=i, y=j)

        game_state = GameState(mapp)
        Controller = ClusterController(width, height)
        Controller.getClustersRolling(width, height, game_state)

        return_result = []
        for key, val in Controller.clusterDict.items():
            current_cluster = []
            for cell in val.cells:
                current_cluster.append([cell.pos.x, cell.pos.y])
            return_result.append(current_cluster)

        assert return_result == cluster

        perimeter_returned = [
            [cell[0], cell[1]]
            for cell in Controller.clusterDict[0].get_perimeter(game_state)
        ]
        assert perimeter_returned == perimeter


test_instance = TestClass()
test_instance.test_one()
