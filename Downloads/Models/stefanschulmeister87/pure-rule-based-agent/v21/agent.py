import numpy as np
import time
from datetime import datetime
from lux.game import Game
from lux.game_map import Cell, RESOURCE_TYPES
from lux.constants import Constants
from lux.game_constants import GAME_CONSTANTS
from lux import annotate
import random
import math
from collections import deque
from enum import Enum

class Cartographer:
    def __init__(self, lux_map, player, opponent, observation):
        self.observation = observation
        self.height = lux_map.height
        self.width = lux_map.width
        self.map = lux_map
        self.player = player
        self.opponent = opponent
        self.city_map = np.zeros([self.width, self.height], np.int16)
        self.unit_map = np.zeros([self.width, self.height], np.int16)
        self.fuel_map = np.zeros([self.width, self.height], np.int16)
        self.resource_map = np.zeros([self.width, self.height], str)
        self.harvesting_map = np.zeros([self.width, self.height], HarvestingTile)
        self.resource_clusters = []
        map_size_dict = {12: "S", 16: "M", 24: "L", 32: "XL"}
        self.map_size = map_size_dict[self.width]
        self.territory_map = None

    def map_battlefield(self):
        self.build_city_map()
        self.build_unit_map()
        self.build_fuel_map()
        self.build_resource_map()
        self.build_harvesting_map()

    def build_territory_map(self):
        """
        Only works if both initial cities are alive. Use this in turn one and save the output globally.
        """
        territory_map = np.zeros([self.width, self.height], np.int16)
        player_city = None
        opponent_city = None

        if len(self.player.cities.keys()) > 0:
            player_city = self.player.cities[list(self.player.cities.keys())[0]]
        if len(self.opponent.cities.keys()) > 0:
            opponent_city = self.opponent.cities[list(self.opponent.cities.keys())[0]]

        if (player_city is not None) and (opponent_city is not None):
            # get mirror axis:
            if player_city.citytiles[0].pos.x == opponent_city.citytiles[0].pos.x:
                # mirror_axis --> x
                for x in range(self.width):
                    for y in range(self.height):
                        if y < self.height / 2:
                            if player_city.cityid == "c_1":
                                territory_map[x][y] = 1
                            else:
                                territory_map[x][y] = 2
                        else:
                            if player_city.cityid == "c_1":
                                territory_map[x][y] = 2
                            else:
                                territory_map[x][y] = 1
            else:
                # mirror_axis --> y
                for x in range(self.width):
                    for y in range(self.height):
                        if x < self.width / 2:
                            if player_city.cityid == "c_1":
                                territory_map[x][y] = 1
                            else:
                                territory_map[x][y] = 2
                        else:
                            if player_city.cityid == "c_1":
                                territory_map[x][y] = 2
                            else:
                                territory_map[x][y] = 1
        else:
            print("can't build territory_map")
        return territory_map

    def build_resource_cluster(self):
        """
        Builds list of ResourceClusters.
        Note: clusters that connect diagonal are not counting as one cluster.
        :return:
        """
        directions = [[0, 1], [1, 0], [0, -1], [-1, 0]]
        mapped_tiles = set()
        for x in range(self.width):
            for y in range(self.height):
                if (x, y) not in mapped_tiles:
                    cell = self.map.get_cell(x, y)
                    if cell.has_resource():
                        # build cluster:
                        resource_cluster = ResourceCluster(map_size=self.map_size)
                        resource_tile = ResourceTile(pos_tuple=(x, y), resource_type=self.resource_map[x][y],
                                                     fuel_amount=self.fuel_map[x][y])
                        resource_cluster.add_resource_tile(resource_tile=resource_tile)
                        mapped_tiles.add((x, y))
                        cluster_discovered = False
                        tiles_to_visit = set()
                        while not cluster_discovered:
                            for d in directions:
                                new_x = x + d[0]
                                new_y = y + d[1]
                                if (new_x, new_y) not in mapped_tiles:
                                    # check if tile is on map.
                                    if (0 <= new_x < self.width) and (0 <= new_y < self.height):
                                        cell = self.map.get_cell(new_x, new_y)
                                        if cell.has_resource():
                                            resource_tile = ResourceTile(pos_tuple=(new_x, new_y),
                                                                         resource_type=self.resource_map[new_x][new_y],
                                                                         fuel_amount=self.fuel_map[new_x][new_y])
                                            resource_cluster.add_resource_tile(resource_tile=resource_tile)
                                            mapped_tiles.add((new_x, new_y))
                                            tiles_to_visit.add((new_x, new_y))
                            if len(tiles_to_visit) == 0:
                                cluster_discovered = True
                            else:
                                x, y = tiles_to_visit.pop()
                        resource_cluster.check_surrounding(map_width=self.width, map_height=self.height,
                                                           city_map=self.city_map, player=self.player,
                                                           opponent=self.opponent, unit_map=self.unit_map,
                                                           territory_map=self.territory_map)
                        self.resource_clusters.append(resource_cluster)
        # add clusters that are diagonally connected together.
        all_connected = False
        combined_clusters = []
        clusters = set(self.resource_clusters.copy())
        joint_clusters = set()
        if len(clusters) > 0:
            while not all_connected:
                cluster = clusters.pop()
                combined = False
                if cluster not in joint_clusters:
                    other_clusters = [c for c in clusters if c not in joint_clusters]
                    for other_cluster in other_clusters:
                        for r1_tile in cluster.resource_tiles:
                            for r2_tile in other_cluster.resource_tiles:
                                dist = self.distance(origin=r1_tile.pos, destination=r2_tile.pos)
                                if dist == 2:
                                    # check for diagonal connection.
                                    if (r1_tile.pos[0] != r2_tile.pos[0]) and (r1_tile.pos[1] != r2_tile.pos[1]):
                                        # --> diagonal connection:
                                        joint_clusters.add(other_cluster)
                                        joint_clusters.add(cluster)
                                        cluster += other_cluster
                                        combined = True
                                        break

                if combined:
                    clusters.add(cluster)
                else:
                    if cluster not in joint_clusters:
                        combined_clusters.append(cluster)
                if len(clusters) == 0:
                    all_connected = True
        self.resource_clusters = combined_clusters

    def build_city_map(self):
        """
        Return a grid with values 0, 1 or 2
        0: No city on tile
        1: Player city on tile
        2. Opponent city on tile
        """
        player_city_tiles = {(tile.pos.x, tile.pos.y) for city in self.player.cities.values()
                             for tile in city.citytiles}
        opponent_city_tiles = {(tile.pos.x, tile.pos.y) for city in self.opponent.cities.values()
                               for tile in city.citytiles}

        for x in range(self.width):
            for y in range(self.height):
                if (x, y) in player_city_tiles:
                    self.city_map[x][y] = 1
                elif (x, y) in opponent_city_tiles:
                    self.city_map[x][y] = 2

    def build_unit_map(self):
        """
        Returns a grid with values 0, 1 or 2.
        0: No unit on tile
        1: Player unit on tile
        2: opponent unit on tile
        """
        player_unit_tiles = {(unit.pos.x, unit.pos.y) for unit in self.player.units}
        opponent_unit_tiles = {(unit.pos.x, unit.pos.y) for unit in self.opponent.units}

        for x in range(self.width):
            for y in range(self.height):
                if (x, y) in player_unit_tiles:
                    self.unit_map[x][y] = 1
                elif (x, y) in opponent_unit_tiles:
                    self.unit_map[x][y] = 2

    def build_fuel_map(self):
        """
        Returns a grid with the amount of fuel left on each cell from a players perspective. This included the players
        research level.
        Can be used for resource cluster evaluation.
        """
        for x in range(self.width):
            for y in range(self.height):
                cell = self.map.get_cell(x, y)
                if cell.has_resource():
                    if cell.resource.type == Constants.RESOURCE_TYPES.WOOD:
                        self.fuel_map[x][y] = 1 * cell.resource.amount
                    elif cell.resource.type == Constants.RESOURCE_TYPES.COAL and self.player.researched_coal():
                        self.fuel_map[x][y] = 10 * cell.resource.amount
                    elif cell.resource.type == Constants.RESOURCE_TYPES.URANIUM and self.player.researched_uranium():
                        self.fuel_map[x][y] = 40 * cell.resource.amount

    def build_resource_map(self):
        """
        Returns a grid with values w, c or u.
        w: Wood
        c: Coal
        u: Uranium
        """
        for x in range(self.width):
            for y in range(self.height):
                cell = self.map.get_cell(x, y)
                if cell.has_resource():
                    if cell.resource.type == Constants.RESOURCE_TYPES.WOOD:
                        self.resource_map[x][y] = "w"
                    elif cell.resource.type == Constants.RESOURCE_TYPES.COAL:
                        self.resource_map[x][y] = "c"
                    elif cell.resource.type == Constants.RESOURCE_TYPES.URANIUM:
                        self.resource_map[x][y] = "u"

    def build_harvesting_map(self):
        """
        Builds a grid of HarvestingTiles. The research status of the player is taken into account.
        """
        for x in range(self.width):
            for y in range(self.height):
                cell = self.map.get_cell(x, y)
                fuel_value_per_turn = 0
                collection_amount_per_turn = 0
                num_wood = 0
                num_coal = 0
                num_uranium = 0
                for k, direction in GAME_CONSTANTS["DIRECTIONS"].items():
                    adjacent_pos = cell.pos.translate(direction, 1)
                    if (0 <= adjacent_pos.x < self.width) and (0 <= adjacent_pos.y < self.height):
                        # adjacent_pos is still on map
                        adjacent_cell = self.map.get_cell(adjacent_pos.x, adjacent_pos.y)
                        if adjacent_cell.has_resource():
                            if adjacent_cell.resource.type == Constants.RESOURCE_TYPES.WOOD:
                                fuel_value_per_turn += 20
                                collection_amount_per_turn += 20
                                num_wood += 1
                            elif adjacent_cell.resource.type == Constants.RESOURCE_TYPES.COAL and \
                                    self.player.researched_coal():
                                fuel_value_per_turn += 50
                                collection_amount_per_turn += 5
                                num_coal += 1
                            elif adjacent_cell.resource.type == Constants.RESOURCE_TYPES.URANIUM and \
                                    self.player.researched_uranium():
                                fuel_value_per_turn += 80
                                collection_amount_per_turn += 2
                                num_uranium += 1

                self.harvesting_map[x][y] = HarvestingTile(fuel_value_per_turn, collection_amount_per_turn, num_wood,
                                                           num_coal, num_uranium)

    @staticmethod
    def distance(origin, destination):
        """
        Return Manhatten distance between two points.
        :param origin: list [x, y]
        :param destination: list [x, y]
        :return: int
        """
        return np.abs(origin[0] - destination[0]) + np.abs(origin[1] - destination[1])

    @staticmethod
    def distance_with_obstacles(obstacles_map, origin, destination):
        """
        Return the shortest distance between two point without moving over obstacles given a grid of obstacles. An
        obstacles is identified by any value greater then 0 in the given grid.
        If no way is found we return 1000.
        """
        obstacles_map[origin[0]][origin[1]] = 0  # the starting position cant be an obstacle
        directions = [[0, 1], [1, 0], [0, -1], [-1, 0]]
        q = deque()
        origin.append(0)
        q.append(origin)  # [row, col, distance]

        visited = set()
        while len(q) > 0:
            cr, cc, c_dist = q.popleft()
            if cr == destination[0] and cc == destination[1]:
                return c_dist
            if obstacles_map[cr][cc] >= 1:  #
                # obstacle
                continue
            for direction in directions:
                nr, nc = cr + direction[0], cc + direction[1]
                if 0 <= nr < len(obstacles_map) and 0 <= nc < len(obstacles_map[0]) and (nr, nc) not in visited:
                    q.append([nr, nc, c_dist + 1])
                    visited.add((nr, nc))
        return 1000

    @staticmethod
    def distance_to_district(pos, district_mayor):
        """
        Return the distance and the closes tile from a position to a district.
        :param pos: pos tupel
        :param district_mayor: DistrictMayor
        :return: distance, pos
        """
        min_tile_dist = np.inf
        closest_tile_pos = None
        for city_tile in district_mayor.city.citytiles:
            dist = Cartographer.distance(origin=[pos[0], pos[1]], destination=[city_tile.pos.x, city_tile.pos.y])
            if dist < min_tile_dist:
                min_tile_dist = dist
                closest_tile_pos = (city_tile.pos.x, city_tile.pos.y)
        if min_tile_dist < 100:
            return min_tile_dist, closest_tile_pos
        else:
            return 1000, None

    @staticmethod
    def distance_cluster_to_district(cluster, district_mayor):
        """
        Calculate the min distance between a ResourceCluster and a DistrictMajor
        :param cluster: ResourceCluster
        :param district_mayor: DistrictMajor
        :return: Min distance between both clusters as distance.
        """
        min_dist = np.inf
        dist = 1000
        for resource_tile in cluster.resource_tiles:
            dist, _ = Cartographer.distance_to_district(pos=resource_tile.pos, district_mayor=district_mayor)
            if dist < min_dist:
                min_dist = dist
        return dist

    @staticmethod
    def distance_to_cluster(pos, cluster):
        min_tile_dist = np.inf
        closest_tile_pos = None
        resource_positions = set([rt.pos for rt in cluster.resource_tiles])
        for tile_pos in cluster.surrounding_tiles_pos.union(resource_positions):
            dist = Cartographer.distance(origin=pos, destination=tile_pos)
            if dist < min_tile_dist:
                min_tile_dist = dist
                closest_tile_pos = tile_pos
        if closest_tile_pos is not None:
            return min_tile_dist, closest_tile_pos
        else:
            return 1000, None

    @staticmethod
    def distance_cluster_to_cluster(cluster1, cluster2):
        connection_tile_pos_1 = None
        connection_tile_pos_2 = None
        min_dist = np.inf
        for tile_pos in cluster1.surrounding_tiles_pos:
            dist, tile_2_pos = Cartographer.distance_to_cluster(pos=tile_pos, cluster=cluster2)
            if dist < min_dist:
                min_dist = dist
                connection_tile_pos_1 = tile_pos
                connection_tile_pos_2 = tile_2_pos
        if connection_tile_pos_1 is not None:
            return min_dist, connection_tile_pos_1, connection_tile_pos_2
        else:
            return 1000, None, None

    @staticmethod
    def distance_district_to_district(district1, district2):
        connection_tile_pos_1 = None
        connection_tile_pos_2 = None
        min_dist = np.inf
        for tile_pos in district1.city_tiles_positions:
            dist, tile_2_pos = Cartographer.distance_to_district(pos=tile_pos, district_mayor=district2)
            if dist < min_dist:
                min_dist = dist
                connection_tile_pos_1 = tile_pos
                connection_tile_pos_2 = tile_2_pos
        if connection_tile_pos_1 is not None:
            return min_dist, connection_tile_pos_1, connection_tile_pos_2
        else:
            return 1000, None, None


class HarvestingTile:
    """
    Stores harvesting information per tile.
    fuel_value_per_turn: The maximal amount of collected fuel per turn.
    collection_amount_per_turn: the amount of collectible resources per turn.
    num_wood: num reachable wood tiles
    num_coal: num reachable coal tiles
    num_uranium: num reachable uranium tiles
    """
    def __init__(self, fuel_value_per_turn, collection_amount_per_turn, num_wood, num_coal, num_uranium):
        self.fuel_value_per_turn = fuel_value_per_turn
        self.collection_amount_per_turn = collection_amount_per_turn
        self.num_wood = num_wood
        self.num_coal = num_coal
        self.num_uranium = num_uranium


class ResourceTile:
    def __init__(self, pos_tuple, resource_type, fuel_amount):
        self.pos = pos_tuple
        self.resource_type = resource_type
        self.fuel_amount = fuel_amount


class ResourceCluster:
    def __init__(self, map_size):
        self.map_size = map_size
        self.resource_tiles = set()
        self.size = 0
        self.fuel_amount = 0
        self.cluster_type = None
        self.surrounding_tiles_pos = set()
        self.territory = None  # can be None p for player o for opponent or b for both
        self.captured_by = None  # can be None p for player o for opponent or b for both
        self.attached_player_city_tiles_pos = set()
        self.attached_opponent_city_tiles_pos = set()
        self.unguarded_expansion_pos = set()
        self.close_opponent_units = []
        self.min_dist_to_opponent_unit = np.inf
        self.num_surrounding_units = 0
        self.num_surrounding_opponent_units = 0
        self.num_possible_expansions = 0
        self.num_wood_tiles = 0
        self.num_send_blockers = 0

    def __add__(self, other):
        """
        Adds two clusters together.
        """
        new_cluster = ResourceCluster(map_size=self.map_size)
        new_cluster.resource_tiles = set.union(self.resource_tiles, other.resource_tiles)
        new_cluster.size = self.size + other.size
        new_cluster.fuel_amount = self.fuel_amount + other.fuel_amount
        combined_cluster_types = sorted(set([t for t in self.cluster_type] + [t for t in other.cluster_type]))
        new_cluster.cluster_type = "".join(combined_cluster_types)
        new_cluster.surrounding_tiles_pos = set.union(self.surrounding_tiles_pos, other.surrounding_tiles_pos)
        if self.territory == other.territory:
            new_cluster.territory = self.territory
        else:
            new_cluster.territory = "b"

        if self.captured_by == other.captured_by:
            if self.captured_by is None:
                new_cluster.captured_by = None
            else:
                new_cluster.captured_by = self.captured_by
        elif self.captured_by != other.captured_by:
            if self.captured_by is None:
                new_cluster.captured_by = other.captured_by
            elif other.captured_by is None:
                new_cluster.captured_by = self.captured_by
            else:
                new_cluster.captured_by = "b"

        new_cluster.attached_player_city_tiles_pos = set.union(self.attached_player_city_tiles_pos,
                                                               other.attached_player_city_tiles_pos)
        new_cluster.attached_opponent_city_tiles_pos = set.union(self.attached_opponent_city_tiles_pos,
                                                                 other.attached_opponent_city_tiles_pos)
        new_cluster.unguarded_expansion_pos = set.union(self.unguarded_expansion_pos, other.unguarded_expansion_pos)
        new_cluster.min_dist_to_opponent_unit = min(self.min_dist_to_opponent_unit, other.min_dist_to_opponent_unit)
        new_cluster.num_surrounding_units = self.num_surrounding_units + other.num_surrounding_units
        new_cluster.num_surrounding_opponent_units = \
            self.num_surrounding_opponent_units + other.num_surrounding_opponent_units
        new_cluster.num_possible_expansions = self.num_possible_expansions + other.num_possible_expansions
        new_cluster.num_wood_tiles = self.num_wood_tiles + other.num_wood_tiles
        new_cluster.num_send_blockers = self.num_send_blockers + other.num_send_blockers
        return new_cluster

    def unit_is_in_cluster(self, unit):
        is_part_of_cluster = False
        if (unit.pos.x, unit.pos.y) in [rt.pos for rt in self.resource_tiles]:
            is_part_of_cluster = True
        if (unit.pos.x, unit.pos.y) in self.surrounding_tiles_pos:
            is_part_of_cluster = True
        return is_part_of_cluster

    def add_resource_tile(self, resource_tile):
        self.resource_tiles.add(resource_tile)
        self.size += 1
        self.fuel_amount += resource_tile.fuel_amount
        if self.cluster_type is None:
            self.cluster_type = resource_tile.resource_type
        else:
            if resource_tile.resource_type not in self.cluster_type:
                self.cluster_type += resource_tile.resource_type
                sorted_items = sorted(self.cluster_type)
                self.cluster_type = "".join(sorted_items)

    def check_surrounding(self, map_width, map_height, city_map, player, opponent, unit_map, territory_map):
        surrounding_tiles_pos = set()
        resource_tiles_pos = [(rt.pos[0], rt.pos[1]) for rt in self.resource_tiles]
        directions = [[0, 1], [1, 0], [0, -1], [-1, 0]]
        for tile in self.resource_tiles:
            for d in directions:
                new_x = tile.pos[0] + d[0]
                new_y = tile.pos[1] + d[1]
                if (0 <= new_x < map_width) and (0 <= new_y < map_height):
                    if ((new_x, new_y) not in surrounding_tiles_pos) and ((new_x, new_y) not in resource_tiles_pos):
                        surrounding_tiles_pos.add((new_x, new_y))
        self.surrounding_tiles_pos = surrounding_tiles_pos

        for pos in surrounding_tiles_pos:
            if city_map[pos[0]][pos[1]] == 1:
                # player city_tile
                self.attached_player_city_tiles_pos.add(pos)
            elif city_map[pos[0]][pos[1]] == 2:
                # opponent city_tile
                self.attached_opponent_city_tiles_pos.add(pos)
            else:
                # free spot:
                self.num_possible_expansions += 1

        if len(self.attached_player_city_tiles_pos) > 0:
            if len(self.attached_opponent_city_tiles_pos) > 0:
                self.captured_by = "b"
            else:
                self.captured_by = "p"
        else:
            if len(self.attached_opponent_city_tiles_pos) > 0:
                self.captured_by = "o"

        # check for closes opponent.
        opponent_obstacle_map = city_map.copy()
        for x in range(len(city_map)):
            for y in range(len(city_map[0])):
                if unit_map[x][y] == 1:
                    opponent_obstacle_map[x][y] = 1
        # --> units and city tiles count as obstacle for opponent units.
        """
        Note: If no unit is around 10 tiles the default value will be 100,
        """
        close_opponent_units = []
        min_dist = 100
        for tile in resource_tiles_pos:
            for unit in opponent.units:
                dist = Cartographer.distance(origin=(unit.pos.x, unit.pos.y), destination=tile)
                if dist < 8:
                    dist = Cartographer.distance_with_obstacles(origin=[unit.pos.x, unit.pos.y], destination=tile,
                                                                obstacles_map=opponent_obstacle_map)
                    if dist < min_dist:
                        if self.map_size in ["S", "M"]:
                            if dist <= 3:
                                close_opponent_units.append([unit, dist])
                        elif self.map_size in ["L", "XL"]:
                            if dist <= 6:
                                close_opponent_units.append([unit, dist])
                        min_dist = dist
        close_opponent_units = sorted(close_opponent_units, key=lambda k: k[1])
        close_opponent_units = [c[0] for c in close_opponent_units]
        self.close_opponent_units = close_opponent_units
        self.min_dist_to_opponent_unit = min_dist

        # check number of surrounding player units.
        for pos in surrounding_tiles_pos:
            if unit_map[pos[0]][pos[1]] == 1:
                if city_map[pos[0]][pos[1]] == 1:
                    # city tile --> check for more then on unit if
                    num_units = len([u for u in player.units if (u.pos.x, u.pos.y) == pos])
                    self.num_surrounding_units += num_units
                else:
                    self.num_surrounding_units += 1
            else:
                # no unit is standing on this tile:
                if city_map[pos[0]][pos[1]] == 0:
                    # no city tile on this position
                    self.unguarded_expansion_pos.add(pos)
        for pos in resource_tiles_pos:
            if unit_map[pos[0]][pos[1]] == 1:
                self.num_surrounding_units += 1

        # check number of surrounding opponent units.
        if self.min_dist_to_opponent_unit < 2:

            for pos in self.surrounding_tiles_pos.union(resource_tiles_pos):
                if unit_map[pos[0]][pos[1]] == 2:
                    if city_map[pos[0]][pos[1]] == 2:
                        num_units = len([u for u in opponent.units if (u.pos.x, u.pos.y) == pos])
                        self.num_surrounding_opponent_units += num_units
                    else:
                        self.num_surrounding_opponent_units += 1

        # check territory:
        for tile in self.resource_tiles:
            if territory_map[tile.pos[0]][tile.pos[1]] == 1:
                # player territory
                if self.territory is None:
                    self.territory = "p"
                elif self.territory == "o":
                    self.territory = "b"
                    break
            if territory_map[tile.pos[0]][tile.pos[1]] == 2:
                # opponent territory
                if self.territory is None:
                    self.territory = "o"
                elif self.territory == "p":
                    self.territory = "b"
                    break

        # count_num_wood_tiles:
        self.num_wood_tiles = len([rt for rt in self.resource_tiles if rt.resource_type == "w"])

    def show(self):
        print(30 * "-")
        print(f"size: {self.size}")
        print(f"fuel_amount: {self.fuel_amount}")
        print(f"cluster_type: {self.cluster_type}")
        print(f"territory: {self.territory}")
        print(f"captures_by: {self.captured_by}")
        print(f"min_dist_to_opponent_unit: {self.min_dist_to_opponent_unit}")
        print(f"num_surrounding_units: {self.num_surrounding_units}")
        print(f"num_possible_expansions: {self.num_possible_expansions}")
        print(f"unguarded_expansion_pos: {self.unguarded_expansion_pos}")
        print(f"num_wood_tiles: {self.num_wood_tiles}")
        print(30 * "-")
        
        
class MovementOfficer:
    def __init__(self, step, city_map, unit_map, player, opponent, lux_map, harvesting_map):
        self.direction_dict = {"e": [1, 0], "s": [0, 1], "w": [-1, 0], "n": [0, -1]}
        self.step = step
        self.unit_map = unit_map
        self.city_map = city_map
        self.player = player
        self.opponent = opponent
        self.obstacles_map = np.zeros([len(self.unit_map), len(self.unit_map[0])], np.int16)
        self.builder_obstacles_map = np.zeros([len(self.unit_map), len(self.unit_map[0])], np.int16)
        self.map = lux_map
        self.harvesting_map = harvesting_map
        self.movement_map = np.zeros([len(self.unit_map), len(self.unit_map[0])], object)
        self.day = None

    def build_movement_map(self, orders):
        """
        Builds movement map with orders in mind.
        A builder which is at his building position cant be moved even if he hast cd == 0.
        :param orders: List of orders.
        :return:
        """
        for player_unit in self.player.units:
            if player_unit.cooldown > 0:
                # unit wont move this turn;
                self.movement_map[player_unit.pos.x][player_unit.pos.y] = "x"
            else:
                # check if unit could be moved and if it has an order to do something.
                unit_order = [o for o in orders if o.unit == player_unit]
                if len(unit_order) == 1:
                    # unit could move but has an order
                    if (unit_order[0].order_type == OrderType.Expansion) and (unit_order[0].dist == 0):
                        # builder standing on his expansion spot --> can't be moved
                        self.movement_map[player_unit.pos.x][player_unit.pos.y] = "x"
                    elif unit_order[0].dist == 0:
                        # todo: potential for improvements. Move harvesting units for example in favor of other
                        #  harvesting units
                        # some other unit with order and cd 0 that sits on its destination.
                        self.movement_map[player_unit.pos.x][player_unit.pos.y] = "x"
                    else:
                        # some units with move order that is not at its destination. Move this unit first.
                        self.movement_map[player_unit.pos.x][
                            player_unit.pos.y] = f"p {player_unit.id} {1}"  # 1 == Has order
                else:
                    # unit could move and has no order
                    self.movement_map[player_unit.pos.x][player_unit.pos.y] = f"p {player_unit.id} {0}"  # 0 == No order

        for opp_unit in self.opponent.units:
            if opp_unit.cooldown > 0:
                # unit wont move this turn;
                self.movement_map[opp_unit.pos.x][opp_unit.pos.y] = "x"
            else:
                # unit could move
                # Todo: We could think about running in enemy units to  block them. For now we just see them as obstacle
                self.movement_map[opp_unit.pos.x][opp_unit.pos.y] = "x"

        for x in range(len(self.city_map)):
            for y in range(len(self.city_map[0])):
                if self.city_map[x][y] == 2:
                    # opponent city tile:
                    self.movement_map[x][y] = "x"

                elif self.city_map[x][y] == 1:
                    # player city tile
                    self.movement_map[x][y] = "c"
        return self.movement_map

    def get_possible_directions_for_unit(self, unit, destination, is_builder, is_returning_harvester,
                                         use_obstacle_maps=False):
        """
        Greedy algorithm
        """
        possible_directions_dict = {}
        distances = []

        if is_builder:
            cargo = 100 - unit.get_cargo_space_left()
            if cargo < 60:
                # treat builder as normal unit:
                is_builder = False

        for key, value in self.direction_dict.items():
            new_x, new_y = unit.pos.x + value[0], unit.pos.y + value[1]
            if (0 <= new_x < self.map.width) and (0 <= new_y < self.map.height):
                # new position is on map. --> check for obstacles:
                if use_obstacle_maps:
                    if is_builder or is_returning_harvester:
                        if self.builder_obstacles_map[new_x][new_y] == 0:
                            dist = Cartographer.distance(origin=[new_x, new_y], destination=destination)
                            distances.append(dist)
                            possible_directions_dict[key] = [(new_x, new_y), dist, (new_x == destination[0])
                                                             or (new_y == destination[1])]
                            # new_position, distance to destination, on the same axis
                    else:
                        if self.obstacles_map[new_x][new_y] == 0:
                            dist = Cartographer.distance(origin=[new_x, new_y], destination=destination)
                            distances.append(dist)
                            possible_directions_dict[key] = [(new_x, new_y), dist, (new_x == destination[0])
                                                             or (new_y == destination[1])]
                        # new_position, distance to destination, on the same axis

                else:
                    # use movement_map
                    if self.movement_map[new_x][new_y] != "x":
                        if is_builder or is_returning_harvester:
                            if self.movement_map[new_x][new_y] != "c":
                                dist = Cartographer.distance(origin=[new_x, new_y], destination=destination)
                                distances.append(dist)
                                possible_directions_dict[key] = [(new_x, new_y), dist, (new_x == destination[0])
                                                                 or (new_y == destination[1])]
                                # new_position, distance to destination, on the same axis
                        else:
                            dist = Cartographer.distance(origin=[new_x, new_y], destination=destination)
                            distances.append(dist)
                            possible_directions_dict[key] = [(new_x, new_y), dist, (new_x == destination[0])
                                                             or (new_y == destination[1])]
                            # new_position, distance to destination, on the same axis

        shortest_directions = [k for k, v in possible_directions_dict.items() if v[1] == min(distances)]
        if len(shortest_directions) > 1:
            # exclude opposite direction
            shortest_directions_ex_opposite = [k for k in shortest_directions if not possible_directions_dict[k][2]]
            if len(shortest_directions_ex_opposite) > 1:
                # choose random direction between the other
                possible_directions = shortest_directions_ex_opposite
            elif len(shortest_directions_ex_opposite) == 1:
                possible_directions = shortest_directions_ex_opposite
            else:
                # len(shortest_directions_ex_opposite) == 0
                # this means that the destination is diagonal to the origin.
                # So we choose one at random.
                possible_directions = shortest_directions
        elif len(shortest_directions) == 1:
            possible_directions = shortest_directions
        else:
            possible_directions = []

        return possible_directions

    def move_units(self, move_orders):
        actions = []
        unit_movement_options = set()
        for order in move_orders:

            directions = self.get_possible_directions_for_unit(
                unit=order.unit, destination=order.pos,
                is_returning_harvester=((order.order_type == OrderType.Harvest_Return) and (order.dist > 1)),
                is_builder=order.order_type == OrderType.Expansion)

            unit_movement_options.add(MovementOptions(order=order, directions=directions,
                                                      harvesting_map=self.harvesting_map,
                                                      movement_map=self.movement_map, day=self.day))

        def try_to_move_unit_without_order(unit_id, blocked_positions):
            """
            Check if there is a spot the unit can move without blocking any other move option.
            :return:
            """
            can_be_moved = False
            evasive_pos = ()
            evasive_direction = None
            unit = [u for u in self.player.units if u.id == unit_id]
            if len(unit) > 0:
                unit = unit[0]
                for direction, delta in self.direction_dict.items():
                    new_x = unit.pos.x + delta[0]
                    new_y = unit.pos.y + delta[1]
                    if (0 <= new_x < self.map.width) and (0 <= new_y < self.map.height):
                        if (self.movement_map[new_x][new_y] == "c" or self.movement_map[new_x][new_y] == 0) and \
                                ((new_x, new_y) not in blocked_positions):
                            evasive_direction = direction
                            evasive_pos = (new_x, new_y)
                            can_be_moved = True
                            break
            if can_be_moved:
                # We move the unit and update our Movement map. Other units cant be moved to this position.
                self.movement_map[evasive_pos[0]][evasive_pos[1]] = "x"
                if self.movement_map[unit.pos.x][unit.pos.y][0] == "p":
                    self.movement_map[unit.pos.x][unit.pos.y] = 0
                for v in unit_movement_options:
                    v.remove_option_direction(pos=(evasive_pos[0], evasive_pos[1]))
                    v.build_options_from_directions()
                actions.append(unit.move(evasive_direction))
                return True
            else:
                return False

        def assign_position(move_action):
            """
            Moves unit from move action to best direction
            Removes the given spots from all other Move Actions after adding the move actions.
            Resets all other options for the moved unit.
            :param move_action: MoveAction
            :return:
            """
            actions.append(move_action.order.unit.move(move_action.best_option.direction))
            self.movement_map[move_action.best_option.pos[0]][move_action.best_option.pos[1]] = "x"
            if self.movement_map[move_action.order.unit.pos.x][move_action.order.unit.pos.y][0] == "p":
                # update movement map. If this unit was a blocker --> remove it. Otherwise it was standing on a city and
                # we leave the entry as "c.
                self.movement_map[move_action.order.unit.pos.x][move_action.order.unit.pos.y] = 0
            for v in unit_movement_options:
                v.remove_option_direction(pos=move_action.best_option.pos)
                v.build_options_from_directions()

        loop_move_actions = set()

        def stay(move_action):
            self.movement_map[move_action.order.unit.pos.x][move_action.order.unit.pos.y] = "x"
            for v in unit_movement_options:
                v.remove_option_direction(pos=(move_action.order.unit.pos.x, move_action.order.unit.pos.y))
                v.build_options_from_directions()

        def try_to_execute_move_action(move_action):

            if move_action.can_move and not move_action.best_option.collision:
                # has a best option that will not collide with other units.
                # check if another unit wants to go there:
                possible_collision = False
                critical_collision = False
                for v in unit_movement_options:
                    if v.order.unit.id != move_action.order.unit.id:
                        if v.includes_option_with_position(pos=move_action.best_option.pos):
                            if v.num_options == 1:
                                possible_collision = True
                                critical_collision = True
                            else:
                                possible_collision = True
                if critical_collision:

                    if move_action.num_options == 1:
                        # we have a critical collision and both unit can only move on that single tile.
                        # --> prefer builder
                        if move_action.order.order_type == OrderType.Expansion:
                            # if i am a builder --> take the spot. Else --> don't move
                            assign_position(move_action=move_action)
                        else:
                            # i am not a builder and therefor i will not move
                            stay(move_action)
                    elif move_action.num_options > 1:
                        # we have a collision and at least one unit can only move on that one tile in our best option.
                        # But we have other option. Try them first.
                        move_action.remove_option_direction(pos=move_action.best_option.pos)
                        move_action.build_options_from_directions()
                        try_to_execute_move_action(move_action=move_action)
                else:
                    # no critical collision
                    if possible_collision:
                        # we have a possible collision but all other units have at least one additional option.
                        # --> just move
                        assign_position(move_action=move_action)
                    else:
                        # no collision at all. We can move:
                        assign_position(move_action=move_action)
            elif move_action.can_move and move_action.best_option.collision:
                # we have a best option but we will collide with other units.
                if move_action.best_option.collision_unit_has_order:
                    # our_best_option will collide with another unit with an order.
                    if move_action in loop_move_actions:
                        # we are in a loop --> try to move this unit if possible:
                        if move_action.num_options > 1:
                            # we have additional options: --> remove best option and add updated move action.
                            loop_move_actions.remove(move_action)
                            move_action.remove_option_direction(pos=move_action.best_option.pos)
                            move_action.build_options_from_directions()
                            try_to_execute_move_action(move_action=move_action)
                        else:
                            # we have only one or zero move action.
                            stay(move_action)
                    else:
                        # first time seeing this move action. Try to move blocking unit with order first:
                        blocking_unit_move_action = [mo for mo in unit_movement_options if mo.order.unit.id ==
                                                     move_action.best_option.collision_unit_id]
                        if len(blocking_unit_move_action) > 0:
                            blocking_unit_move_action = blocking_unit_move_action[0]
                            unit_movement_options.add(move_action)
                            loop_move_actions.add(move_action)
                            unit_movement_options.remove(blocking_unit_move_action)
                            try_to_execute_move_action(move_action=blocking_unit_move_action)
                        else:
                            print(f"WARNING: step: ({self.step}). Something went wrong while moving.")
                else:
                    # our best_option will collide with another unit with no order.
                    # try to move blocking unit
                    possible_taken_positions = set()
                    for v in unit_movement_options:
                        # don't move on current positions of units with orders
                        possible_taken_positions.add((v.order.unit.pos.x, v.order.unit.pos.y))
                        if len(v.options) > 0:
                            for o in v.options:
                                possible_taken_positions.add(o.pos)

                    moved_unit = try_to_move_unit_without_order(unit_id=move_action.best_option.collision_unit_id,
                                                                blocked_positions=possible_taken_positions)
                    if moved_unit:
                        # we moved the blocking unit aside and can move now:
                        assign_position(move_action=move_action)
                    else:
                        # we cant move the blocking unit.
                        if move_action.num_options > 1:
                            # we have additional options: --> remove best option and add updated move action.
                            move_action.remove_option_direction(pos=move_action.best_option.pos)
                            move_action.build_options_from_directions()
                            try_to_execute_move_action(move_action=move_action)
                        else:
                            # don't move at all:
                            stay(move_action)
            else:
                # we have nowhere to go and this means that this unit is an obstacle. --> remove all options with the
                # given position of the unit
                stay(move_action)

        all_units_moved = False
        while not all_units_moved:
            if len(unit_movement_options) == 0:
                all_units_moved = True
            else:
                move_action = unit_movement_options.pop()
                try_to_execute_move_action(move_action=move_action)

        return actions

    def build_obstacles_maps(self):
        """
        Builds obstacles maps and builder_obstacles_map bases on cities and units.
        Considers units with cd 0 not as obstacle.
        :return:
        """
        for x in range(len(self.city_map)):
            for y in range(len(self.city_map[0])):
                if self.city_map[x][y] == 2:
                    # opponent city tile:
                    self.obstacles_map[x][y] = 2
                    self.builder_obstacles_map[x][y] = 2
                elif self.city_map[x][y] == 1:
                    # player city tile
                    self.builder_obstacles_map[x][y] = 1
                else:
                    # no city tile:
                    if self.unit_map[x][y] == 2:
                        # opponent unit:
                        unit = [u for u in self.opponent.units if (u.pos.x, u.pos.y) == (x, y)][0]
                        if unit.cooldown > 0:
                            # unit won't move in this turn
                            self.obstacles_map[x][y] = 2
                            self.builder_obstacles_map[x][y] = 2
                    elif self.unit_map[x][y] == 1:
                        # player unit:
                        unit = [u for u in self.player.units if (u.pos.x, u.pos.y) == (x, y)][0]
                        if unit.cooldown > 0:
                            # unit won't move in this turn
                            self.obstacles_map[x][y] = 1
                            self.builder_obstacles_map[x][y] = 1


class MovementOptions:
    def __init__(self, order, directions, harvesting_map, movement_map, day):
        self._direction_dict = {"e": [1, 0], "s": [0, 1], "w": [-1, 0], "n": [0, -1]}
        self.order = order
        self.directions = directions
        self.harvesting_map = harvesting_map
        self.movement_map = movement_map
        self.day = day
        self.num_options = 0
        self.best_option = None
        self.can_move = False
        self.options = None
        self.build_options_from_directions()

    def reset_option(self):
        """
        after we moved a unit its option will be clear that none of them will collide with other move actions
        :return:
        """
        self.num_options = 0
        self.directions = []
        self.best_option = None
        self.can_move = False
        self.options = None

    def includes_option_with_position(self, pos):
        """
        Checks if a given position is part of an option and if it can be removed and the unit can still move.
        :param pos:
        :return:
        """
        if self.options is not None:
            pos_option = [o for o in self.options if o.pos == pos]
            if len(pos_option) == 0:
                # no option with given position
                return False
            else:
                return True

    def remove_option_direction(self, pos):
        if self.includes_option_with_position(pos=pos):
            option_to_remove = [o for o in self.options if o.pos == pos][0]
            new_possible_directions = [d for d in self.directions if d != option_to_remove.direction]
            self.directions = new_possible_directions

    def build_options_from_directions(self):
        self.options = []
        self.best_option = None
        max_direction_value = 0

        for direction in self.directions:
            collision_unit_id = None
            collision_unit_has_order = False
            new_pos = (self.order.unit.pos.x + self._direction_dict[direction][0],
                       self.order.unit.pos.y + self._direction_dict[direction][1])
            # define direction value

            if self.order.order_type == OrderType.Expansion:
                if self.order.unit.get_cargo_space_left() > 0:
                    direction_value = self.harvesting_map[new_pos[0]][new_pos[1]].collection_amount_per_turn
                else:
                    direction_value = 0
            elif self.order.order_type == OrderType.Harvest_Go:
                direction_value = self.harvesting_map[new_pos[0]][new_pos[1]].fuel_value_per_turn
            else:
                direction_value = 0

            if isinstance(self.movement_map[new_pos[0]][new_pos[1]], str) and \
                    self.movement_map[new_pos[0]][new_pos[1]][0] == "p":
                # ['p', 'u_15', '1']
                collision_info = self.movement_map[new_pos[0]][new_pos[1]].split()
                collision_unit_id = collision_info[1]
                collision_unit_has_order = bool(int(collision_info[2]))
                collision = True
            else:
                collision = False
            if direction_value > max_direction_value:
                max_direction_value = direction_value
            self.options.append(
                MoveOption(direction=direction, pos=new_pos, value=direction_value, collision=collision,
                           collision_unit_id=collision_unit_id, collision_unit_has_order=collision_unit_has_order))
        # remove options that would kill units at night:
        if not self.day:
            # unit wont survive night if next step is not a harvesting spot.
            if self.order.unit.get_cargo_space_left() >= 60:
                possible_options = []
                for option in self.options:
                    if self.harvesting_map[option.pos[0]][option.pos[1]].collection_amount_per_turn >= 4:
                        possible_options.append(option)
                self.options = possible_options

        if len(self.options) > 1:
            # get_options with max direction value:
            best_options = [o for o in self.options if o.value == max_direction_value]
            if len(best_options) > 1:
                # more then one optimal option: --> exclude collision moves
                best_no_collision_options = [o for o in best_options if not o.collision]
                if len(best_no_collision_options) == 0:
                    best_option = best_options[0]
                elif len(best_no_collision_options) == 1:
                    best_option = best_no_collision_options[0]
                else:
                    # > 1
                    best_option = best_no_collision_options[0]
            else:
                # we have one option with max direction value:
                best_option = best_options[0]
        elif len(self.options) == 1:
            # single option
            best_option = self.options[0]
        else:
            # no movement option
            best_option = None
        self.best_option = best_option
        if self.best_option is not None:
            self.can_move = True
        else:
            self.can_move = False
        self.num_options = len(self.options)

    def show(self):
        print(30*"*")
        print(f"num_options: {self.num_options}")
        print(f"best_option: {self.best_option}")
        print(f"can_move: {self.can_move}")


class MoveOption:
    def __init__(self, direction, pos, value, collision, collision_unit_id=None, collision_unit_has_order=None):
        self.direction = direction
        self.pos = pos
        self.value = value
        self.collision = collision
        self.collision_unit_id = collision_unit_id
        self.collision_unit_has_order = collision_unit_has_order

    def __str__(self):
        return f"d: {self.direction}, pos: {self.pos}, value: {self.value}, collision: {self.collision}"


class ExpansionOfficer:

    def __init__(self, lux_map, city_map, harvesting_grid, builder_obstacles_map, obstacles_map, resource_cluster,
                 movement_officer):
        """
        :param lux_map: A lux map object.
        :param city_map: A grid with 0, 1 and 2 values. (0 for no city, 1 for player city and 2 for opponent city.
        :param harvesting_grid: A grid of of HarvestingTile objects
        """
        self.height = lux_map.height
        self.width = lux_map.width
        self.map = lux_map
        self.city_map = city_map
        self.harvesting_grid = harvesting_grid
        self.builder_obstacles_map = builder_obstacles_map
        self.obstacles_map = obstacles_map
        self.expansion_map = np.zeros([self.width, self.height], np.int32)
        self.strategic_expansion_map = np.zeros([self.width, self.height], np.int32)
        self.resource_cluster = resource_cluster
        self.movement_officer = movement_officer
        self.district_mayors = None

    def get_number_of_free_expansion_spots(self):
        """
        Counts the number of free expansion spots from the expansion map before returning it.
        :return:
        """
        number_of_free_expansion_spots = 0
        for x in range(self.width):
            for y in range(self.height):
                if self.expansion_map[x][y] > 0:
                    number_of_free_expansion_spots += 1
        return number_of_free_expansion_spots

    def build_expansion_maps(self, strategy_information, units):
        self.build_expansion_map()
        self.build_strategic_expansion_map(strategy_information=strategy_information, units=units)

    def build_expansion_map(self):
        """
        Builds a grid of possible expansion spots with specific expansion values depending on the amount of attached
        resource tiles.
        """
        for x in range(self.width):
            for y in range(self.height):
                cell = self.map.get_cell(x, y)
                if not cell.has_resource() and self.city_map[x][y] == 0:
                    # cell has no resource tiles and there is no city build on it ---> possible expansion spot.
                    harvesting_tile = self.harvesting_grid[x][y]
                    if (harvesting_tile.num_wood + harvesting_tile.num_coal + harvesting_tile.num_uranium) > 0:
                        expansion_value = 1
                    else:
                        expansion_value = 0
                    self.expansion_map[x][y] = expansion_value

    def update_expansion_maps(self, assigned_expansion_spots: list):
        """
        All assigned_spots will be removed from the expansion_map. (set to 0).
        :param assigned_expansion_spots: List of ExpansionSpots.
        :return:  updated expansion_map.
        """
        if len(assigned_expansion_spots) > 0:
            for spot in assigned_expansion_spots:
                self.expansion_map[spot.spot_pos[0]][spot.spot_pos[1]] = 0
                self.strategic_expansion_map[spot.spot_pos[0]][spot.spot_pos[1]] = 0

    def find_strategic_expansions(self, unit, max_number):

        if ((len(self.district_mayors) == 1) and (self.district_mayors[0].size == 1)) \
                or (len(self.district_mayors) == 0):
            # if we have no cities or only one of size one we are simply looking for the fastest expansion.
            exp_spots = self.find_fastest_expansion_for_unit(unit=unit, max_number=max_number,
                                                             expansion_map=self.expansion_map)
        else:
            # we have at least one city of size 2 or more cities of arbitrary size.
            # at this point we care about not building to much around small clusters and not building inside fully
            # captures clusters. --> we optimise our expansion map.
            exp_spots = self.find_fastest_expansion_for_unit(unit=unit, max_number=max_number,
                                                             expansion_map=self.strategic_expansion_map)
        return exp_spots

    def build_strategic_expansion_map(self, strategy_information, units):
        strategic_expansion_map = self.expansion_map.copy()
        """
        Move to cole before it is researched:
        """
        for x in range(self.width):
            for y in range(self.height):
                if self.city_map[x][y] == 0:
                    cell = self.map.get_cell(x, y)
                    is_possible_coal_expansion_spot = False
                    for direction, delta in self.movement_officer.direction_dict.items():
                        adjacent_pos = cell.pos.translate(direction, 1)
                        if (0 <= adjacent_pos.x < self.width) and (0 <= adjacent_pos.y < self.height):
                            # adjacent_pos is still on map
                            adjacent_cell = self.map.get_cell(adjacent_pos.x, adjacent_pos.y)
                            if adjacent_cell.has_resource() and \
                                    adjacent_cell.resource.type == Constants.RESOURCE_TYPES.COAL:
                                is_possible_coal_expansion_spot = True
                    if is_possible_coal_expansion_spot and \
                            not cell.has_resource() and strategy_information.player_research_points > 40:
                        strategic_expansion_map[x][y] = 1
        """
        Move to uranium before it is researched:
        """
        for x in range(self.width):
            for y in range(self.height):
                if self.city_map[x][y] == 0:
                    cell = self.map.get_cell(x, y)
                    is_uranium_expansion = False
                    for direction, delta in self.movement_officer.direction_dict.items():
                        adjacent_pos = cell.pos.translate(direction, 1)
                        if (0 <= adjacent_pos.x < self.width) and (0 <= adjacent_pos.y < self.height):
                            # adjacent_pos is still on map
                            adjacent_cell = self.map.get_cell(adjacent_pos.x, adjacent_pos.y)
                            if adjacent_cell.has_resource() and \
                                    adjacent_cell.resource.type == Constants.RESOURCE_TYPES.URANIUM:
                                is_uranium_expansion = True
                    if is_uranium_expansion and \
                            not cell.has_resource() and strategy_information.player_research_points > 180:
                        strategic_expansion_map[x][y] = 1

        """
        Add strategic expansion from district mayor expansions:
        """
        for dist_major in self.district_mayors:
            other_district_mayors = [o_dist_major for o_dist_major in self.district_mayors
                                     if o_dist_major != dist_major]
            positions = dist_major.get_strategic_expansion_positions(other_district_mayors=other_district_mayors,
                                                                     harvesting_map=self.harvesting_grid, units=units,
                                                                     strategic_information=strategy_information)
            for pos in positions:
                strategic_expansion_map[pos[0]][pos[1]] = 1

        for cluster in self.resource_cluster:
            """
            """
            # don't build more then one city tile at uranium or coal cluster if no opponent is around:
            if ((cluster.captured_by == "p") or (cluster.captured_by == "b")) and ("w" not in cluster.cluster_type)\
                    and (cluster.min_dist_to_opponent_unit > 6):
                for pos in cluster.surrounding_tiles_pos:
                    # exclude all expansion positions if they are not attached to wood tiles.
                    if self.harvesting_grid[pos[0]][pos[1]].num_wood == 0:
                        strategic_expansion_map[pos[0]][pos[1]] = 0

            """
            Handle player wood cluster:
            Don't over expand. We want to reserve wood as long as possible without slowing down our research speed.
            """
            if ((cluster.captured_by == "p") and ("w" in cluster.cluster_type)) \
                    and (cluster.min_dist_to_opponent_unit > 10):
                max_num_expansions = cluster.size - len(cluster.attached_player_city_tiles_pos)
                if max_num_expansions <= 0:
                    for pos in cluster.surrounding_tiles_pos:
                        strategic_expansion_map[pos[0]][pos[1]] = 0

            if ((cluster.captured_by == "p") and ("w" in cluster.cluster_type)) \
                    and (cluster.min_dist_to_opponent_unit > 4) and (strategy_information.step > 30):

                # get attached district mayors:
                attached_district_majors = set()
                for dist_major in self.district_mayors:
                    for pos in cluster.attached_player_city_tiles_pos:
                        if pos in dist_major.city_tiles_positions:
                            attached_district_majors.add(dist_major)

                # stop expanding wood cluster_cities (min size 3) if there would die from the expansion after
                # coal is researched.
                if strategy_information.player_research_status > 0:
                    for att_dist_mayor in attached_district_majors:
                        if (att_dist_mayor.num_possible_expansions == 0) and (att_dist_mayor.size > 2):
                            for pos in att_dist_mayor.expansion_positions:
                                strategic_expansion_map[pos[0]][pos[1]] = 0

                # stop expanding directly on wood clusters if uranium is researched.
                # TODO: REMOVE FOR BETTER LOGIC
                if strategy_information.player_research_status == 2:
                    for pos in cluster.surrounding_tiles_pos:
                        strategic_expansion_map[pos[0]][pos[1]] = 0

                # leave door open to closest coal or uranium cluster
                # start by finding the closest coal or uranium cluster (if there is one in range.)
                cu_clusters = [c for c in self.resource_cluster if ("u" in c.cluster_type) or ("c" in c.cluster_type)]

                close_cu_clusters = []
                for cu_cluster in cu_clusters:
                    dist, _, _ = Cartographer.distance_cluster_to_cluster(cluster1=cluster, cluster2=cu_cluster)
                    if dist < 6:
                        close_cu_clusters.append(cu_cluster)

                # Todo: Set num openings numbers recording to cluster size
                num_openings = 0
                for cu_cluster in close_cu_clusters:
                    # try to find best opening position for this cluster.
                    min_dist = np.inf
                    opening_pos = None
                    for pos in cluster.surrounding_tiles_pos:
                        if self.city_map[pos[0]][pos[1]] == 0:
                            dist, _ = Cartographer.distance_to_cluster(pos=pos, cluster=cu_cluster)
                            if dist < min_dist:
                                min_dist = dist
                                opening_pos = pos
                    if (opening_pos is not None) and (num_openings < 2):
                        num_openings += 1
                        strategic_expansion_map[opening_pos[0], opening_pos[1]] = 0

                if num_openings < 2:
                    # we want at least 2 openings per cluster
                    # even if we do not have a close by expansion spot it makes sense to keep a door open to connect
                    # attached cities. But we need to protect this gate.
                    num_further_openings = 2 - num_openings
                    for pos in cluster.surrounding_tiles_pos:
                        if num_further_openings > 0:
                            if self.city_map[pos[0], pos[1]] == 0:
                                strategic_expansion_map[pos[0], pos[1]] = 0
                                num_further_openings -= 1

            if ((cluster.captured_by == "p") and ("w" in cluster.cluster_type))\
                    and (strategy_information.step > 30):
                """
                Ensure that we defend our cluster against enemies. --> Wall building.
                Wall against center or against enemy.
                """
                num_possible_expasnion_tasks = cluster.num_surrounding_units
                num_expansion_tiles = len(cluster.surrounding_tiles_pos)
                positions_with_dit_to_opp = []
                for pos in cluster.surrounding_tiles_pos:
                    #for unit in opponent_units:
                        pass

        self.strategic_expansion_map = strategic_expansion_map

    def find_fastest_expansion_time_from_pos(self, pos, expansion_map, harvesting_map, radius):
        """
        Find's the fastest time to expand if on the given position would stand a unit with cargo = 0.
        The idea is to check expansion times from city tiles to decide where to spawn a unit.
        Restriction. This could lead to an performance issue, so we restrict ourself to positions within distance.
        :param pos: pos tuple
        :param expansion_map: map with expansion values.
        :param harvesting_map: harvesting map from Cartographer
        :param radius: The max radius we are looking for expansion spots.
        """
        min_building_time = np.inf
        for x in range(self.width):
            for y in range(self.height):
                if expansion_map[x][y] > 0:
                    simple_dist = Cartographer.distance(origin=[pos[0], pos[1]], destination=[x, y])
                    if simple_dist <= radius:
                        real_dist = Cartographer.distance_with_obstacles(origin=[pos[0], pos[1]], destination=[x, y],
                                                                         obstacles_map=self.builder_obstacles_map)
                        expansion_spot_collection_amount = harvesting_map[x][y].collection_amount_per_turn
                        building_time = np.inf
                        if real_dist == 1:
                            # spot is next to given position:
                            if expansion_spot_collection_amount > 0:
                                time_to_harvest = int(math.ceil(100 / expansion_spot_collection_amount))
                                building_time = time_to_harvest
                            """
                            Note: If we build a unit (City tiles are first in line), this unit can move in the same 
                            turn and collect at its destination. --> building tile harvesting time in destination.
                            (Max harvesting value in neighbor expansion spot is 60 so no need for max(time, 2).
                            """
                        elif real_dist > 1:
                            # spot is more then one tile away.
                            # try to find best next position
                            possible_spots = []
                            best_spot = None
                            min_dist = np.inf
                            for key, value in self.movement_officer.direction_dict.items():
                                new_x, new_y = x + value[0], y + value[1]
                                if (0 <= new_x < self.map.width) and (0 <= new_y < self.map.height):
                                    new_real_distance = Cartographer.distance_with_obstacles(
                                        origin=[new_x, new_y], destination=[x, y],
                                        obstacles_map=self.builder_obstacles_map)
                                    if new_real_distance < min_dist:
                                        min_dist = new_real_distance
                                    if self.builder_obstacles_map[x][y] == 0:
                                        # free spot:
                                        new_spot_collection_amount = harvesting_map[new_x][new_y].\
                                            collection_amount_per_turn
                                        possible_spots.append([(x, y), new_real_distance, new_spot_collection_amount])
                                    elif self.city_map[x][y] == 1:
                                        # player city tile --> we add 0 as spot harvesting amount.
                                        possible_spots.append([(new_x, new_y), new_real_distance, 0])
                            if len(possible_spots) == 1:
                                best_spot = possible_spots[0]
                            elif len(possible_spots) > 1:
                                # select spots with min distance (greedy)
                                min_dist = sorted(possible_spots, key=lambda k: k[1])[0]
                                possible_spots = [spot for spot in possible_spots if spot[1] == min_dist]
                                if len(possible_spots) == 1:
                                    best_spot = possible_spots[0]
                                elif len(possible_spots) > 1:
                                    # take spot with best collection amount:
                                    max_collection_amount = sorted(possible_spots, key=lambda k: k[2], reverse=True)[0]
                                    best_spot = [spot for spot in possible_spots if spot[2] == max_collection_amount][0]

                            if best_spot is not None:
                                new_spot_collection_amount = harvesting_map[best_spot[0][0]][best_spot[0][1]]. \
                                    collection_amount_per_turn
                                harvesting_amount = new_spot_collection_amount * 2 + 2 * best_spot[2]
                                if harvesting_amount >= 100:
                                    building_time = 2 * best_spot[1]
                                    # 2 + distance
                                else:
                                    new_spot_harvesting_amount = 2 * new_spot_collection_amount
                                    missing_fuel = 100 - new_spot_harvesting_amount
                                    if missing_fuel <= 0:
                                        print("WARNING: Missing Fuel is below zero!!!")
                                    if expansion_spot_collection_amount > 0:
                                        time_to_harvest = int(math.ceil(missing_fuel /
                                                                        expansion_spot_collection_amount))
                                        building_time = time_to_harvest + 2 * best_spot[2]

                        if building_time < min_building_time:
                            min_building_time = building_time
        return min_building_time

    def find_fastest_expansion_for_unit(self, unit, max_number, expansion_map):
        """
        :param max_number: The maximum number of returned expansion spots
        :param unit: Lux game unit
        :param expansion_map: map with expansion values.
        :return: List of sorted expansion spots
        """
        if unit.get_cargo_space_left() == 0 and expansion_map[unit.pos.x][unit.pos.y] > 0:
            # Todo: At night we could think about moving closer to expansions near by that are closer to enemies
            exp_spot = ExpansionSpot(spot_pos=[unit.pos.x, unit.pos.y], unit=unit,
                                     city_grid=self.city_map, harvesting_map=self.harvesting_grid,
                                     builder_obstacles_map=self.builder_obstacles_map, obstacles_map=self.obstacles_map)
            exp_spot.time_to_build = unit.cooldown
            exp_spots = [exp_spot]
        elif unit.get_cargo_space_left() == 0 and expansion_map[unit.pos.x][unit.pos.y] == 0:
            # find closest spots ( closest means fastest if unit has a full cargo.
            exp_spots = []
            for x in range(self.width):
                for y in range(self.height):
                    if expansion_map[x][y] > 0:
                        exp_spots.append(ExpansionSpot(spot_pos=[x, y], unit=unit, city_grid=self.city_map,
                                                       harvesting_map=self.harvesting_grid,
                                                       builder_obstacles_map=self.builder_obstacles_map,
                                                       obstacles_map=self.obstacles_map))
            if len(exp_spots) > 0:
                exp_spots = sorted(exp_spots, key=lambda k: k.dist, reverse=False)
                for exp_spot in exp_spots:
                    time_to_walk = unit.cooldown + 2 * exp_spot.dist
                    exp_spot.time_to_build = time_to_walk
                exp_spots = sorted(exp_spots, key=lambda k: k.time_to_build, reverse=False)
                exp_spots = exp_spots[:max_number]

        else:
            exp_spots = []
            for x in range(self.width):
                for y in range(self.height):
                    if expansion_map[x][y] > 0:
                        if self.harvesting_grid[x][y].collection_amount_per_turn > 0:
                            exp_spots.append(ExpansionSpot(spot_pos=[x, y], unit=unit, city_grid=self.city_map,
                                                           harvesting_map=self.harvesting_grid,
                                                           builder_obstacles_map=self.builder_obstacles_map,
                                                           obstacles_map=self.obstacles_map))

            if len(exp_spots) > 0:
                exp_spots = sorted(exp_spots, key=lambda k: k.dist, reverse=False)
                for exp_spot in exp_spots:
                    # cargo until next possible step
                    cargo = 100 - unit.get_cargo_space_left() + unit.cooldown * exp_spot.origin_harvesting_amount

                    # add cargo from traveling.
                    """
                    Note: We do not take more the the next step (the next tile) into account.
                    """
                    if exp_spot.dist == 1:
                        # easy case: expansion spot i neighbor tile.
                        cargo += 2 * exp_spot.spot_collection_amount
                    else:
                        # expansion spot is more then one tile away. We add the farming amount of the first tile in the
                        # expansion direction times 2 (unit needs to stand there for 2 round until it can move again
                        # is 0 again).

                        # try to find best next position
                        best_next_pos = None

                        directions = self.movement_officer.get_possible_directions_for_unit(
                            unit=unit, destination=exp_spot.spot_pos, is_builder=True, is_returning_harvester=False,
                            use_obstacle_maps=True)
                        max_direction_value = 0
                        new_positions_with_values = []
                        for direction in directions:
                            new_pos = (unit.pos.x + self.movement_officer.direction_dict[direction][0],
                                       unit.pos.y + self.movement_officer.direction_dict[direction][1])
                            # define direction value

                            if unit.get_cargo_space_left() > 0:
                                direction_value = self.movement_officer.harvesting_map[new_pos[0]][
                                    new_pos[1]].collection_amount_per_turn
                            else:
                                direction_value = 0
                            if direction_value > max_direction_value:
                                max_direction_value = direction_value
                            new_positions_with_values.append([direction_value, new_pos])

                        if len(new_positions_with_values) > 0:
                            best_next_pos = [pos_and_val[1] for pos_and_val in new_positions_with_values if
                                             pos_and_val[0] == max_direction_value][0]

                        if best_next_pos is not None:
                            # farming amount from next cell + farming amount from expansion spot if we find a next pos.
                            cargo += 2 * exp_spot.spot_collection_amount \
                                     + 2 * self.harvesting_grid[best_next_pos[0]][
                                         best_next_pos[1]].collection_amount_per_turn
                        else:
                            # if we don't find a next position.
                            cargo += 2 * exp_spot.spot_collection_amount

                    # calculate building time
                    if cargo >= 100:
                        # by the time the unit can build he will have enough material to build so if it moves directly
                        # to the spot
                        time = unit.cooldown + 2 * exp_spot.dist
                    else:
                        # unit needs to farm at building spot, so we add the spot_harvesting_amount until 100 is reached
                        missing_material = 100 - cargo
                        if exp_spot.spot_collection_amount > 0:
                            # harvesting at spot location:
                            time_to_harvest = int(math.ceil(missing_material / exp_spot.spot_collection_amount))
                        else:
                            # todo: 100 is only a dummy value
                            time_to_harvest = 100
                        time_to_walk = unit.cooldown + 2 * exp_spot.dist
                        time = time_to_walk + time_to_harvest

                    exp_spot.time_to_build = time

                # sort by time_to_build
                exp_spots = sorted(exp_spots, key=lambda k: k.time_to_build, reverse=False)
                exp_spots = exp_spots[:max_number]
        return exp_spots


class ExpansionSpot:
    """
    Holds all information about an expansion spot.
    """
    def __init__(self, spot_pos, unit, city_grid, harvesting_map, builder_obstacles_map, obstacles_map):
        self.id = f"{spot_pos[0]}{spot_pos[1]}"
        self.spot_pos = spot_pos
        self.unit = unit
        self.city_grid = city_grid
        self.harvesting_map = harvesting_map
        self.origin_pos = [unit.pos.x, unit.pos.y]
        if city_grid[unit.pos.x][unit.pos.y] > 0:
            # unit standing on city tile :
            self.origin_harvesting_amount = 0
        else:
            self.origin_harvesting_amount = harvesting_map[unit.pos.x][unit.pos.y].collection_amount_per_turn
        self.spot_collection_amount = harvesting_map[spot_pos[0]][spot_pos[1]].collection_amount_per_turn

        self.harvesting_pos = self.find_harvesting_spot()
        self.dist = self.calculate_distance(builder_obstacles_map=builder_obstacles_map, obstacles_map=obstacles_map)
        self.time_to_build = None

    def find_harvesting_spot(self):
        """
        NOTE USED FOR NOW
        :return:
        """
        if (self.spot_collection_amount == 0) and (self.unit.get_cargo_space_left() != 0):
            # find closest farming spot near unit
            # look around building unit
            min_dist = np.inf
            closest_spot = None
            closest_spot_pos = None
            for x in range(len(self.city_grid)):
                for y in range(len(self.city_grid[0])):
                    if self.harvesting_map[x][y].num_wood > 0:
                        simple_dist = Cartographer.distance(origin=self.origin_pos, destination=[x, y])
                        if simple_dist < min_dist:
                            min_dist = simple_dist
                            closest_spot = self.harvesting_map[x][y]
                            closest_spot_pos = (x, y)
                        elif simple_dist < min_dist + 2:
                            if self.harvesting_map[x][y].collection_amount_per_turn > closest_spot.collection_amount_per_turn + 10:
                                # we do not adjust min_dist here!
                                closest_spot = self.harvesting_map[x][y]
                                closest_spot_pos = (x, y)
            if closest_spot is not None:
                harvesting_pos = closest_spot_pos
            else:
                harvesting_pos = self.spot_pos
        else:
            # spot_collection_amount < 20 or unit has full cargo.
            harvesting_pos = self.spot_pos
        return harvesting_pos

    def calculate_distance(self, builder_obstacles_map, obstacles_map):
        """
        Calculate distance to expansions spot. If a unit has at least 60 cargo we dont want to walk over city tiles.
        Further moire if the distance is more then 8 we simply use the simple distance for performance reasons.
        (Performance reasons)
        We always move to the harvesting position. If we have a full cargo or the spot pos is a good harvesting spot
        we will move to the building spot.
        :return: int
        """
        simple_dist = Cartographer.distance(origin=self.origin_pos, destination=self.harvesting_pos)

        cargo = 100 - self.unit.get_cargo_space_left()
        if cargo >= 60:
            obstacles_map = builder_obstacles_map
        else:
            obstacles_map = obstacles_map

        if simple_dist < 8:
            dist = Cartographer.distance_with_obstacles(obstacles_map=obstacles_map, origin=self.origin_pos,
                                                        destination=self.harvesting_pos)
        else:
            dist = simple_dist
        return dist

    def show(self):
        """
        Display function for debugging.
        """
        print(30 * "-")
        print("spot_pos: ", self.spot_pos)
        print("harvesting_pos: ", self.harvesting_pos)
        print("origin_pos: ", self.origin_pos)
        print("dist: ", self.dist)
        print("origin_harvesting_amount: ", self.origin_harvesting_amount)
        print("spot_harvesting_amount: ", self.spot_collection_amount)
        print("time_to_build: ", self.time_to_build)
        print(30 * "-")


class CityCouncil:
    """
    Handles information about each city.
    """
    def __init__(self, lux_map, city_map, unit_map, player, harvesting_map, expansion_officer):
        self.map = lux_map
        self.city_map = city_map
        self.unit_map = unit_map
        self.player = player
        self.harvesting_map = harvesting_map
        self.cities = player.cities
        self.expansion_officer = expansion_officer
        self.district_mayors = []

    def distribute_fuel_income(self):
        for dm in self.district_mayors:
            if not dm.survives_all_nights:
                if not dm.survives_next_night:
                    dm.harvesting_priority = dm.size + 1
                else:
                    dm.harvesting_priority = dm.size

    def summon_district_mayors(self, night_steps_left):
        district_mayors = []
        for city in self.cities.values():
            district_mayors.append(DistrictMayor(city=city, harvesting_map=self.harvesting_map,
                                                 night_steps_left=night_steps_left, lux_map=self.map,
                                                 city_map=self.city_map, unit_map=self.unit_map))
        self.district_mayors = district_mayors
        self.distribute_fuel_income()

    def get_district_mayor_by_id(self, city_id):
        """
        Return district major based on his city_id
        :param city_id: str
        :return: DistrictMayor
        """
        return_district_major = None
        for district_mayor in self.district_mayors:
            if district_mayor.city.cityid == city_id:
                return_district_major = district_mayor
                break
        return return_district_major

    def get_district_mayor_by_pos(self, pos):
        """
        Return district major based on pos
        :param pos: tupel
        :return: DistrictMayor
        """
        return_district_major = None
        for district_mayor in self.district_mayors:
            if pos in district_mayor.city_tiles_positions:
                return_district_major = district_mayor
                break
        return return_district_major

    def build_fastest_expanding_units_and_research(self, max_worker_to_build):
        """
        build units where the expansion time is the shortest. It is not always favorable to build a nwe unit if it is
        possible.
        Logic: Build units at tiles with min expansion times. If we have multiple tiles with the same time we choos the
               newest.
       :param : max_worker_to_build: Maximum amount of workers we can build this turn.
        """
        actions = []
        if max_worker_to_build > 0:
            # order city by id: returns list of tuples [[city_id, city], ...] that can be sorted by city_id
            city_ids = [[city.cityid[city.cityid.find("_") + 1:], city] for city in self.cities.values()]
            # sort cities by id:
            cities = sorted(city_ids, key=lambda k: k[0], reverse=True)
            tiles_with_expansion_time_and_age = []
            # [tile, min_expansion_time, age]
            age = 0
            for city in cities:
                for city_tile in reversed(city[1].citytiles):
                    expansion_time = self.expansion_officer.find_fastest_expansion_time_from_pos(
                        pos=(city_tile.pos.x, city_tile.pos.y),
                        expansion_map=self.expansion_officer.strategic_expansion_map,
                        harvesting_map=self.harvesting_map, radius=5)
                    expansion_time += city_tile.cooldown
                    tiles_with_expansion_time_and_age.append([city_tile, expansion_time, age])
                    age += 1
            # sort city_tiles by expansion_time and then by age. --> if we have two tiles with the same expansion value
            # we prefer the city_tile from the newer city.
            tiles_with_expansion_time_and_age = sorted(tiles_with_expansion_time_and_age, key=lambda k: (k[1], k[2]))
            # try to build the units with the first max_worker_to_build city_tiles.
            index = 1
            for tile_info in tiles_with_expansion_time_and_age:
                city_tile = tile_info[0]
                if index <= max_worker_to_build:
                    if city_tile.can_act():
                        action = city_tile.build_worker()
                        actions.append(action)
                else:
                    # research if necessary
                    if not self.player.researched_uranium():
                        action = city_tile.research()
                        actions.append(action)
                index += 1

        else:
            # we cant build workers. So research if possible and necessary:
            for city in self.cities.values():
                for city_tile in city.citytiles:
                    if not self.player.researched_uranium() and city_tile.can_act():
                        action = city_tile.research()
                        actions.append(action)
        return actions

    def build_units_and_research(self, max_worker_to_build):
        """
        NOT USES
        :param max_worker_to_build:
        :return:
        """
        actions = []
        # order city by id: returns list of tuples [[city_id, city], ...] that can be sorted by city_id
        city_ids = [[city.cityid[city.cityid.find("_") + 1:], city] for city in self.cities.values()]
        # sort cities by id:
        cities = sorted(city_ids, key=lambda k: k[0], reverse=True)
        for city in cities:
            # now we loop in reverse to prefer newer city tiles for unit production.
            for city_tile in reversed(city[1].citytiles):
                if city_tile.can_act():
                    if max_worker_to_build > 0:
                        action = city_tile.build_worker()
                        actions.append(action)
                        max_worker_to_build -= 1
                    else:
                        if not self.player.researched_uranium():
                            # We only research until we researched uranium. Then we stop and
                            # don't wast city cd for useless further research points.
                            action = city_tile.research()
                            actions.append(action)
        return actions


class DistrictMayor:
    """"
    Handles information from one city.
    """
    # TODO: Calculate fuel consumption and according booleans for each possible expansion. Will this expansion kill the
    #  city?
    def __init__(self, city, harvesting_map, night_steps_left, lux_map, city_map, unit_map):
        self.origin = [city.citytiles[0].pos.x, city.citytiles[0].pos.y]
        self.city_tiles_positions = set([(tile.pos.x, tile.pos.y) for tile in city.citytiles])
        self.city = city
        self.size = len(city.citytiles)
        self.light_upkeep = city.get_light_upkeep()
        self.survives_next_night = bool((self.light_upkeep * 10) < city.fuel)
        self.survives_all_nights = bool((self.light_upkeep * night_steps_left) < city.fuel)
        self.expansion_positions = self.get_expansion_positions(lux_map=lux_map, city_map=city_map)
        self.free_district_harvesting_spots = []
        self.best_free_harvesting_spot = None
        self.update_district_harvesting_information(harvesting_map=harvesting_map, unit_map=unit_map,
                                                    assigned_positions=[])
        self.fuel_income_per_turn = self.get_fuel_income_per_turn(harvesting_map=harvesting_map, unit_map=unit_map)
        # Resource drops on CityTiles is before CityTiles consume fuel so we add fuel_income_per_turn to city.fuel
        self.district_harvesting_spots = self.get_district_harvesting_spots(harvesting_map=harvesting_map)
        self.harvesting_priority = 0
        self.num_possible_expansions = self.get_min_num_possible_expansions(night_steps_left)

    def get_min_num_possible_expansions(self, night_steps_left):
        if self.survives_all_nights:
            num_possible_expansions = 0
            for i in range(11):
                # max will be 10 but this should be enough
                if bool(((self.light_upkeep + i * 24) * night_steps_left) < self.city.fuel):
                    num_possible_expansions += 1
                else:
                    break
        else:
            num_possible_expansions = 0

        return num_possible_expansions

    def get_strategic_expansion_positions(self, other_district_mayors, units, harvesting_map, strategic_information):
        """
        Logic:
        1) Expand on uranium and coal cities if they would survive the next night
        2) Expand cities that would survive until the end.
        3) Try to wall enemies
        """

        """
        1) Expand on uranium and coal cities if they would survive the next night.
        a) If city.size == 1 --> expand in all possible directions
        b) Else expand in direction of all other clusters with min size 2.
        c) And we ensure that expansion spots ar not only attached to coal or uranium tiles. Otherwise they might be 
            blocked by harvesters.
        d) expand in all directions if its last day and city would survive last night
        """
        def add_positions_close_other_clusters(usable_positions):
            for other_dist_mayor in priority_other_district_mayors:
                min_dist = np.inf
                expansion_pos = None
                for pos in usable_positions:
                    dist, _ = Cartographer.distance_to_district(pos=pos, district_mayor=other_dist_mayor)
                    if dist < min_dist:
                        min_dist = dist
                        expansion_pos = pos
                if expansion_pos is not None:
                    strategic_expansion_positions.add(expansion_pos)

        strategic_expansion_positions = set()
        is_coal_or_uranium_expansion = False
        for ha_spot in self.district_harvesting_spots:
            if ha_spot.includes_coal or ha_spot.includes_uranium:
                is_coal_or_uranium_expansion = True

        priority_other_district_mayors = [dm for dm in other_district_mayors if dm.size >= 2]

        if is_coal_or_uranium_expansion and (self.survives_next_night > 0):
            if self.size == 1:
                """ a) """
                strategic_expansion_positions = self.expansion_positions.copy()
            else:
                """ b) """
                add_positions_close_other_clusters(usable_positions=self.expansion_positions)
                """ c) """
                no_non_c_u_harvesting_expansion_spot = True
                for pos in strategic_expansion_positions:
                    harvesting_tile = harvesting_map[pos[0]][pos[1]]
                    if ((harvesting_tile.num_coal == 0) and (harvesting_tile.num_uranium == 0)) or \
                            harvesting_tile.num_wood > 0:
                        no_non_c_u_harvesting_expansion_spot = False
                        break
                if no_non_c_u_harvesting_expansion_spot:
                    # try to find expansion spot that is not a coal or uranium spot:
                    possible_position = set()
                    for pos in self.expansion_positions:
                        harvesting_tile = harvesting_map[pos[0]][pos[1]]
                        if ((harvesting_tile.num_coal == 0) and (harvesting_tile.num_uranium == 0)) or \
                                harvesting_tile.num_wood > 0:
                            possible_position.add(pos)

                    add_positions_close_other_clusters(usable_positions=possible_position)
                """ d) """
                if strategic_information.step >= 320:
                    for pos in self.expansion_positions:
                        strategic_expansion_positions.add(pos)

        elif is_coal_or_uranium_expansion is False and (self.num_possible_expansions > 0):
            """
            2) Expand cities that would survive until the end.
            a) expand in direction of closest unit with 100 wood if wood survive until the end and also with expansion.
            b) expand in all directions if last night
            """
            """ a) """
            full_cargo_units = [unit for unit in units if unit.get_cargo_space_left() == 0]
            # use only expansion positions that are not attached to a wood cluster.
            possible_expansions_positions = [pos for pos in self.expansion_positions
                                             if harvesting_map[pos[0]][pos[1]].num_wood == 0]
            min_dist = np.inf
            positions = set()
            for unit in full_cargo_units:
                for tile_pos in possible_expansions_positions:
                    dist = Cartographer.distance(origin=(unit.pos.x, unit.pos.y), destination=tile_pos)
                    if dist < min_dist:
                        positions = set()
                        positions.add(tile_pos)
                        min_dist = dist
                    elif dist == min_dist:
                        positions.add(tile_pos)
            for pos in positions:
                strategic_expansion_positions.add(pos)

            """ b) """
            if strategic_information.step >= 320:
                for pos in possible_expansions_positions:
                    strategic_expansion_positions.add(pos)

        return strategic_expansion_positions

    def update_district_harvesting_information(self, harvesting_map, unit_map, assigned_positions):
        """
        Updates free_district_harvesting_spots and best_free_harvesting_spot.
        :param harvesting_map: harvesting map
        :param unit_map: unit map
        :param assigned_positions: list of tuples with positions of taken tiles.
        """
        self.free_district_harvesting_spots = self.get_free_district_harvesting_spots(harvesting_map=harvesting_map,
                                                                                      unit_map=unit_map,
                                                                                      assigned_positions=
                                                                                      assigned_positions)
        if len(self.free_district_harvesting_spots) == 1:
            self.best_free_harvesting_spot = sorted(self.free_district_harvesting_spots,
                                                    key=lambda k: k.harvesting_value, reverse=True)[0]
        elif len(self.free_district_harvesting_spots) > 1:
            self.best_free_harvesting_spot = self.free_district_harvesting_spots[0]
        else:
            self.best_free_harvesting_spot = None

    def get_expansion_positions(self, lux_map, city_map):
        """
        All tiles that would expand this city. Regardless if it would be a good expansion or not.
        :return:
        """
        expansion_positions = set()
        directions = [[1, 0], [0, 1], [-1, 0], [0, -1]]
        for tile in self.city.citytiles:
            for d in directions:
                adjacent_pos = [tile.pos.x + d[0], tile.pos.y + d[1]]
                if (0 <= adjacent_pos[0] < lux_map.width) and (0 <= adjacent_pos[1] < lux_map.height):
                    cell = lux_map.get_cell(tile.pos.x + d[0], tile.pos.y + d[1])
                    if not cell.has_resource() and city_map[tile.pos.x + d[0]][tile.pos.y + d[1]] == 0:
                        expansion_positions.add((tile.pos.x + d[0], tile.pos.y + d[1]))
        return expansion_positions

    def get_district_harvesting_spots(self, harvesting_map):
        """
        Builds a sorted list of HarvestingSpots for this district. Includes only spots with positive harvesting_value.
        :param harvesting_map: Cartographer.harvesting_map
        :return: A sorted list of HarvestingSpots.
        """
        district_harvesting_spots = []
        for tile in self.city.citytiles:
            # city tile is free
            harvesting_tile = harvesting_map[tile.pos.x][tile.pos.y]
            if harvesting_tile.fuel_value_per_turn > 0:
                district_harvesting_spots.append(DistrictHarvestingSpot(pos=(tile.pos.x, tile.pos.y),
                                                                        harvesting_tile=harvesting_tile))
        district_harvesting_spots = sorted(district_harvesting_spots, key=lambda k: k.harvesting_value, reverse=True)
        return district_harvesting_spots

    def get_free_district_harvesting_spots(self, harvesting_map, unit_map, assigned_positions):
        """
        Get all free district harvesting spots bast on the unit map an additional assigned positions.
        :param harvesting_map: harvesting map
        :param unit_map: unit map
        :param assigned_positions: list of tuples with positions of taken tiles.
        :return: a list of DistrictHarvestingSpot with positions and specific harvesting value.
        """

        own_unit_map = unit_map.copy()
        for pos_list in assigned_positions:
            own_unit_map[pos_list[0]][pos_list[1]] = 1

        district_harvesting_spots = []
        for tile in self.city.citytiles:
            if own_unit_map[tile.pos.x][tile.pos.y] == 0:
                # city tile is free
                harvesting_tile = harvesting_map[tile.pos.x][tile.pos.y]
                district_harvesting_spots.append(DistrictHarvestingSpot(pos=(tile.pos.x, tile.pos.y),
                                                                        harvesting_tile=harvesting_tile))
        return district_harvesting_spots

    def get_fuel_income_per_turn(self, harvesting_map, unit_map):
        fuel_income_per_turn = 0
        for tile in self.city.citytiles:
            if unit_map[tile.pos.x][tile.pos.y] == 1:
                # min one unit standing on city tile --> is harvesting for city
                fuel_income_per_turn += harvesting_map[tile.pos.x][tile.pos.y].fuel_value_per_turn
        return fuel_income_per_turn

    def show(self):
        print(30 * "*")
        print("City_id: ", self.city.cityid)
        print("Size: ", self.size)
        print("fuel:", self.city.fuel)
        print("fuel_consumption_per_night: ", self.light_upkeep)
        print("survives_next_night: ", self.survives_next_night)
        print("survives_all_nights: ", self.survives_all_nights)
        print("expansion_positions: ", self.expansion_positions)
        print("fuel_income_per_turn: ", self.fuel_income_per_turn)
        print(30 * "*")


class DistrictHarvestingSpot:
    def __init__(self, pos, harvesting_tile):
        self.pos = pos
        self.harvesting_value = harvesting_tile.fuel_value_per_turn
        self.includes_wood = (harvesting_tile.num_wood > 0)
        self.includes_coal = (harvesting_tile.num_coal > 0)
        self.includes_uranium = (harvesting_tile.num_uranium > 0)

        
class General:
    def __init__(self, cartographer, expansion_officer, movement_officer, city_council, harvesting_officer, actions):
        self.cartographer = cartographer
        self.expansion_officer = expansion_officer
        self.movement_officer = movement_officer
        self.city_council = city_council
        self.harvesting_officer = harvesting_officer
        self.units_cap = sum([len(x.citytiles) for x in cartographer.player.cities.values()])
        self.num_units = len(cartographer.player.units)
        self.free_units = set(cartographer.player.units.copy())
        self.assigned_builder_ids = set()
        self.night_steps_left = 0
        self.steps_until_night = 0
        self.steps_until_day = 0
        self.day = True
        self.actions = actions
        self.orders = []
        self.strategy_information = None
        max_worker_to_build = self.units_cap - self.num_units
        building_and_research_actions = self.city_council.build_units_and_research(
            max_worker_to_build=max_worker_to_build)
        self.actions += building_and_research_actions
        # update num units
        self.num_units = len(cartographer.player.units)
        self.free_units = set(cartographer.player.units.copy())

    def order(self):
        """
        LOGIC:
        1) Units with a huge amount of wodd cant be harvister if coal or uranium is avaliable
        2) Coal and Uranium city harvesting spots have to supported.
        3) Units with huge amounts of Coal or Uranium have to be harvesters
        :return:
        """
        # todo: Early expansion überarbeiten.  (refactor) 76, 26
        # todo: Dont move away from spot that would be taken by enemy. (especially on smaller maps)
        # todo: Expand faster. Multiple units sending to one cluster early on.
        # todo: builder with 100 wood sometimes cant find a way to expansion spots.. use distance with obstacle map!!
        # Todo: das nullen von holz cluster positions cancelt die city expasnions teilweise weg. --> city expansions
        #  müssen ex holz cluster expansions gewählt werden.
        # Todo: units mit 100 Holz laufen teils in cities wenn sie keinen Weg finden und einen city support auftrag
        #  oder etwas anderes bekommen.
        # todo: Expansion in direction of closest expansion opportunity for opponent. Especially on cluster with
        #   territory="b"
        # todo: Distribution fails for seed: 146985625
        # todo: Unit building is not working properly. New cites on new clusters must always produce a unit if possible.
        #       The problem is when cities dye and the unit cap is negative...
        # todo: In der max num unit units for distribution section gibt es viel verbesserungspotenzial.
        # todo: In Orders we only use the normal distance. Is that a problem?
        # todo: add blocking order. --> standing on a specific position to block oppoenten units to move on mosition.
        #   a grid pattern seems to be quite efficeient.

        """
        Support early uran or coal expansion.
        """
        city_units = [u for u in self.free_units if self.cartographer.city_map[u.pos.x][u.pos.y] == 1]
        secured_positions = set()
        for unit in city_units:
            if self.strategy_information.player_research_status == 1:
                # check if coal harvesting spot:
                if self.cartographer.harvesting_map[unit.pos.x][unit.pos.y].num_coal > 0:
                    if (unit.pos.x, unit.pos.y) not in secured_positions:
                        self.assign_order_to_unit(unit=unit, position_tuple=(unit.pos.x, unit.pos.y),
                                                  order_type=OrderType.CitySupport)
                        secured_positions.add((unit.pos.x, unit.pos.y))
            if self.strategy_information.player_research_status == 2:
                # check if coal harvesting spot:
                if self.cartographer.harvesting_map[unit.pos.x][unit.pos.y].num_coal > 0\
                        or self.cartographer.harvesting_map[unit.pos.x][unit.pos.y].num_uranium > 0:
                    if (unit.pos.x, unit.pos.y) not in secured_positions:
                        self.assign_order_to_unit(unit=unit, position_tuple=(unit.pos.x, unit.pos.y),
                                                  order_type=OrderType.CitySupport)
                        secured_positions.add((unit.pos.x, unit.pos.y))
        # get harvesting units

        self.order_unit_distribution()

        if self.strategy_information.num_player_city_tiles > self.strategy_information.num_player_save_city_tiles:
            """
            If we have cities to support we don't want units with substantial amounts of fuel value to switch orders.
            Wood harvester will possible still switch orders.
            """
            harvester = set()
            for unit in self.free_units:
                # get cluster of unit:
                if unit.cargo.coal > 50:
                    unit_cluster = None
                    for cluster in self.cartographer.resource_clusters:
                        if "c" in cluster.cluster_type:
                            cluster_tiles = [rt.pos for rt in cluster.resource_tiles] + \
                                            [t for t in cluster.surrounding_tiles_pos]
                            if (unit.pos.x, unit.pos.y) in cluster_tiles:
                                unit_cluster = cluster
                                break
                    if (unit_cluster is None) or (unit_cluster is not None
                                                and (unit_cluster.min_dist_to_opponent_unit > 6)):
                        # add units to harvesters if they are not part of an coal cluster that is under attack
                        harvester.add(unit)
                if unit.cargo.uranium > 30:
                    harvester.add(unit)
            if len(harvester) > 1:
                self.order_harvesting(units=harvester)

        """
        If a unit is standing on an possible expansion spot and an opponent unit is standing right next to it.
        it should not move.
        """
        check_units = [u for u in self.free_units.copy()
                       if self.cartographer.harvesting_map[u.pos.x][u.pos.y].collection_amount_per_turn > 0]
        for unit in check_units:
            if (self.expansion_officer.expansion_map[unit.pos.x][unit.pos.y] != 0) and (
                    self.expansion_officer.strategic_expansion_map[unit.pos.x][unit.pos.y] == 0):
                # check if enemy unit want on this spot:
                # close by opponent unit:
                opp_unit_close_by = False
                for opp_unit in self.cartographer.opponent.units:
                    dist = Cartographer.distance(origin=(unit.pos.x, unit.pos.y),
                                                 destination=(opp_unit.pos.x, opp_unit.pos.y))
                    if dist <= 2:
                        opp_unit_close_by = True
                        break
                if opp_unit_close_by:
                    self.assign_order_to_unit(unit=unit, position_tuple=(unit.pos.x, unit.pos.y),
                                              order_type=OrderType.ClusterDefence)
            elif (self.expansion_officer.expansion_map[unit.pos.x][unit.pos.y] != 0) and (
                    self.expansion_officer.strategic_expansion_map[unit.pos.x][unit.pos.y] != 0):
                # in this case we should build there.
                spot = ExpansionSpot(spot_pos=[unit.pos.x, unit.pos.y], unit=unit,
                                     city_grid=self.expansion_officer.city_map,
                                     harvesting_map=self.expansion_officer.harvesting_grid,
                                     builder_obstacles_map=self.expansion_officer.builder_obstacles_map,
                                     obstacles_map=self.expansion_officer.obstacles_map)
                self.assign_order_to_unit(unit=spot.unit, position_tuple=spot.harvesting_pos,
                                          order_type=OrderType.Expansion, additional_information=spot)

        if self.steps_until_night < 6:
            # save units that need saving.
            self.order_city_support()
            self.order_expansions()
            self.order_save_spots()
            self.order_unit_blocking()
            self.order_resource_defense()
            self.order_harvesting()
        else:
            self.order_unit_blocking()
            self.order_expansions()
            self.order_resource_defense()
            self.order_city_support()
            self.order_harvesting()

        #self.strategy_information.show()
        #self.print_orders()

    def print_orders(self):
        num_orders = len(self.orders)
        building_orders = [o for o in self.orders if o.order_type == OrderType.Expansion]
        city_support = [o for o in self.orders if o.order_type == OrderType.CitySupport]
        save_spot = [o for o in self.orders if o.order_type == OrderType.SaveSpot]
        harvest_go = [o for o in self.orders if o.order_type == OrderType.Harvest_Go]
        harvest_return = [o for o in self.orders if o.order_type == OrderType.Harvest_Return]
        cluster_defence = [o for o in self.orders if o.order_type == OrderType.ClusterDefence]
        distribution = [o for o in self.orders if o.order_type == OrderType.Distribution]
        blockers = [o for o in self.orders if o.order_type == OrderType.Blocking]
        num_free_units = len(self.free_units)
        print(f"step: {self.cartographer.observation['step']}, units / free: ({self.num_units} / "
              f"{num_free_units}) , num_orders: {num_orders} "
              f"(b: {len(building_orders)}, cs:{len(city_support)}, s: {len(save_spot)}, hg: {len(harvest_go)},"
              f" hr: {len(harvest_return)}, cd: {len(cluster_defence)}, d: {len(distribution)}),"
              f" b: {len(blockers)})")

    def get_distribution_options_for_cluster(self, cluster):
        """
        Builds and returns an ClusterDistributionOptions object.
        We use only wood cluster for distribution.
        status
        """

        cluster_dist_opts = ClusterDistributionOptions(cluster=cluster, units=self.free_units,
                                                       strat_info=self.strategy_information,
                                                       city_council=self.city_council)
        other_clusters = [c for c in self.cartographer.resource_clusters if (c != cluster)
                          and ("w" in c.cluster_type) and (c.size >= 2)]

        for other_cluster in other_clusters:
            dist, origin_tile_pos, destination_tile_pos = Cartographer.distance_cluster_to_cluster(
                cluster1=cluster, cluster2=other_cluster)
            if origin_tile_pos is not None:
                cluster_dist_opts.add_spot(DistributionSpot(other_cluster=other_cluster, dist=dist,
                                                            origin_cluster=cluster,
                                                            origin_tile_pos=origin_tile_pos,
                                                            destination_tile_pos=destination_tile_pos))

        cluster_dist_opts.prioritize_spots()
        return cluster_dist_opts

    def order_unit_distribution(self):
        """
        The idea is to distribute units strategically around the map and thereby expand strategically.
        :return:
        """
        # get all distribution spots

        cluster_unit_mapping = {}
        cluster_distribution_options = []
        for cluster in self.cartographer.resource_clusters:
            if cluster.captured_by in ["p", "b"]:
                if len(cluster.attached_player_city_tiles_pos) >= 2:
                    # try to move to next cluster.
                    cluster_distribution_option = self.get_distribution_options_for_cluster(cluster=cluster)
                    cluster_distribution_option.trim_spots()
                    for unit in cluster_distribution_option.cluster_units:
                        cluster_unit_mapping[unit] = cluster_distribution_option
                    cluster_distribution_options.append(cluster_distribution_option)
        # Now find suitable units for these spots:
        distribution_spots = []

        for cluster in self.cartographer.resource_clusters:
            # we do not want to have multiple units distribute to the same cluster. This results in bad unit
            # distribution and possible bad defence.
            # --> one distribution for one cluster. (take the spot with the closest distance.
            spots_for_cluster = [spot for cluster_dist_opt in cluster_distribution_options for spot in
                                 cluster_dist_opt.distribution_spots if spot.other_cluster == cluster]
            if len(spots_for_cluster) == 1:
                distribution_spots.append(spots_for_cluster[0])
            elif len(spots_for_cluster) >= 1:
                spots_for_cluster = sorted(spots_for_cluster, key=lambda k: k.dist)
                distribution_spots.append(spots_for_cluster[0])

        # first we sort recording to dist and then priority
        distribution_spots = sorted(sorted(distribution_spots, key=lambda k: k.dist),
                                    key=lambda k: k.priority, reverse=True)
        for dist_spot in distribution_spots:
            # find closest unit that can make it.
            min_dist = np.inf
            closest_unit = None
            for unit in self.free_units:
                dist, pos = Cartographer.distance_to_cluster(pos=(unit.pos.x, unit.pos.y),
                                                             cluster=dist_spot.other_cluster)
                if self.get_unit_range(unit) >= dist:
                    if dist < min_dist:
                        min_dist = dist
                        if unit in cluster_unit_mapping.keys():
                            # check if unit is about to populate another wood cluster. This can be the case if two
                            # wood clusters are close together and one unit part of both.
                            is_close_to_wood_cluster = False
                            wood_cluster = [c for c in self.cartographer.resource_clusters
                                            if ("w" in c.cluster_type) and (c != dist_spot.origin_cluster)
                                            and (len(c.attached_player_city_tiles_pos) < 2)
                                            and (c.size >= 2)]
                            for cluster in wood_cluster:
                                cluster_dist, _, _ = Cartographer.distance_cluster_to_cluster(
                                    cluster1=dist_spot.origin_cluster, cluster2=cluster)
                                if cluster_dist > 1:
                                    dist, _ = Cartographer.distance_to_cluster(pos=(unit.pos.x, unit.pos.y),
                                                                               cluster=cluster)
                                    if dist == 0:
                                        is_close_to_wood_cluster = True
                                        break
                            if (closest_unit is not None) and (closest_unit in cluster_unit_mapping.keys()):
                                # reset num_usable_units for the old units cluster
                                cluster_unit_mapping[closest_unit].num_usable_units += 1

                            if (cluster_unit_mapping[unit].num_usable_units > 0)\
                                    and (is_close_to_wood_cluster is False):
                                cluster_unit_mapping[unit].num_usable_units -= 1
                                closest_unit = unit
                        else:
                            # here we need to check if this unit is close to another wood cluster and tries to capture
                            # it. But exclude the origin cluster that the unit was moving from.
                            # get closest cluster:
                            c_min_dist = np.inf
                            closest_dist_cluster = None
                            for cluster_dist_opt in cluster_distribution_options:
                                dist, _ = Cartographer.distance_to_cluster(pos=(unit.pos.x, unit.pos.y),
                                                                           cluster=cluster_dist_opt.cluster)
                                if dist < c_min_dist:
                                    c_min_dist = dist
                                    closest_dist_cluster = cluster_dist_opt

                            if closest_dist_cluster is not None:
                                closest_dist_cluster.num_usable_units -= 1

                            is_close_to_wood_cluster = False
                            wood_cluster = [c for c in self.cartographer.resource_clusters
                                            if ("w" in c.cluster_type) and (c != dist_spot.origin_cluster)
                                            and (len(c.attached_player_city_tiles_pos) < 2)
                                            and (c.size >= 2)]
                            for cluster in wood_cluster:
                                cluster_dist, _, _ = Cartographer.distance_cluster_to_cluster(
                                    cluster1=dist_spot.origin_cluster, cluster2=cluster)
                                if cluster_dist > 1:
                                    dist, _ = Cartographer.distance_to_cluster(pos=(unit.pos.x, unit.pos.y),
                                                                               cluster=cluster)
                                    if dist == 0:
                                        is_close_to_wood_cluster = True
                                        break
                            if is_close_to_wood_cluster is False:
                                if (closest_unit is not None) and (closest_unit in cluster_unit_mapping.keys()):
                                    # reset num_usable_units for the old units cluster
                                    cluster_unit_mapping[closest_unit].num_usable_units += 1
                                closest_unit = unit

            if closest_unit is not None:
                # check if the distribution spot is blocked by opponent city tile.
                dist, pos = Cartographer.distance_to_cluster(pos=(closest_unit.pos.x, closest_unit.pos.y),
                                                             cluster=dist_spot.other_cluster)
                if self.cartographer.city_map[pos[0]][pos[1]] == 2:
                    # tile is blocked: --> find closest free tile:
                    dist_to_closest_free_tile = np.inf
                    closest_free_tile_pos = None
                    for spot in dist_spot.other_cluster.surrounding_tiles_pos:
                        dist = Cartographer.distance_with_obstacles(obstacles_map=self.movement_officer.obstacles_map,
                                                                    origin=[closest_unit.pos.x, closest_unit.pos.y],
                                                                    destination=spot)
                        if dist < dist_to_closest_free_tile:
                            dist_to_closest_free_tile = dist
                            closest_free_tile_pos = spot
                    pos = closest_free_tile_pos
                # check if can harvest at distribution spot
                if (pos is not None) and (self.cartographer.harvesting_map[pos[0]][pos[1]].fuel_value_per_turn < 20):
                    # spot has no harvesting value --> find closest tile with positive harvesting value
                    # This is the case if coal or uranium is part of the cluster and it is not researched jet
                    dist_to_closest_free_tile = np.inf
                    closest_harvesting_tile_pos = None
                    for spot in dist_spot.other_cluster.surrounding_tiles_pos:
                        if self.cartographer.harvesting_map[spot[0]][spot[1]].fuel_value_per_turn >= 20:
                            dist = Cartographer.distance_with_obstacles(
                                obstacles_map=self.movement_officer.obstacles_map,
                                origin=[closest_unit.pos.x, closest_unit.pos.y], destination=spot)
                            if dist < dist_to_closest_free_tile:
                                dist_to_closest_free_tile = dist
                                closest_harvesting_tile_pos = spot
                    pos = closest_harvesting_tile_pos
                if pos is not None:
                    self.assign_order_to_unit(unit=closest_unit, position_tuple=pos,
                                              order_type=OrderType.Distribution)

    def order_resource_defense(self):
        """
        Simply moves units to possible expansion spots to block them for enemy players. Especially useful for player
        wood expansions.
        :return: Simply assigns orders.
        """
        # prefer captures resource tiles.
        # get spots:
        # we order the cluster recording to distance to opponent units.
        clusters_to_defence = [cluster for cluster in self.cartographer.resource_clusters
                               if cluster.captured_by in ["p", "b"]]

        clusters_to_defence = sorted(clusters_to_defence, key=lambda k: k.min_dist_to_opponent_unit)

        defence_positions = set()
        for cluster in clusters_to_defence:
            if (cluster.captured_by == "p") or (cluster.captured_by == "b"):
                for pos in cluster.unguarded_expansion_pos:
                    defence_positions.add(pos)

        # check for free units that are already on a defence position.
        for unit in self.free_units:
            if (unit.pos.x, unit.pos.y) in defence_positions:
                self.assign_order_to_unit(unit=unit, position_tuple=(unit.pos.x, unit.pos.y),
                                          order_type=OrderType.ClusterDefence)
                defence_positions.remove((unit.pos.x, unit.pos.y))

        # find closes free unit for each spot:
        for pos in defence_positions:
            # check if pos can be defended (it has a positive harvesting value)
            if self.cartographer.harvesting_map[pos[0]][pos[1]].collection_amount_per_turn > 4:
                closest_dist = np.inf
                closest_unit = None
                for unit in self.free_units:
                    dist = Cartographer.distance(origin=[unit.pos.x, unit.pos.y], destination=pos)
                    if dist < closest_dist:
                        closest_dist = dist
                        closest_unit = unit
                if closest_unit is not None:
                    unit_will_make_it = False
                    if self.day:
                        unit_range = self.get_unit_range(closest_unit)
                        if unit_range >= closest_dist:
                            unit_will_make_it = True
                    else:
                        # move at night
                        if closest_dist == 1:
                            # unit is next to spot: (check if unit can survive at pos)
                            collection_amount = self.cartographer.harvesting_map[pos[0]][
                                pos[1]].collection_amount_per_turn
                            if collection_amount > 4:
                                unit_will_make_it = True
                        else:
                            # check if default direction leads to a farming cell.
                            cell = self.cartographer.map.get_cell(pos[0], pos[1])
                            direct_direction = closest_unit.pos.direction_to(cell.pos)
                            new_pos = closest_unit.pos.translate(direct_direction, 1)
                            collection_amount = self.cartographer.harvesting_map[new_pos.x][new_pos.y].\
                                collection_amount_per_turn
                            if collection_amount > 4:
                                unit_will_make_it = True
                    if unit_will_make_it:
                        self.assign_order_to_unit(unit=closest_unit, position_tuple=pos,
                                                  order_type=OrderType.ClusterDefence)

    def order_unit_blocking(self):
        # for now we only block units if our our cluster is in danger.
        min_dist_for_blocking = {"S": 3, "M": 3, "L": 6, "XL": 6}
        clusters_to_defence = [rc for rc in self.cartographer.resource_clusters if (rc.captured_by == "p")
                               and (rc.min_dist_to_opponent_unit <= min_dist_for_blocking[self.cartographer.map_size])]

        def unit_is_allowed_to_block(blocker_unit):
            """
            Chacks if a unit is allowed to block other unit.
            1) We need to prevent all units from leaving one cluster
            2) If we have only one unit at a specific cluster this unit can't block. --> this unit needs to build!
            3) If a unit is Distributing to an enemy cluster it is allowed to block incomming units.
            """
            allowed_to_block = False
            unit_clusters = []
            for _cluster in self.cartographer.resource_clusters:
                if _cluster.unit_is_in_cluster(unit=blocker_unit):
                    # units can be part of two clusters!
                    unit_clusters.append(_cluster)
            if len(unit_clusters) == 0:
                # unit is part of no cluster
                allowed_to_block = True
            elif len(unit_clusters) == 1:
                # unit is part of one cluster
                unit_cluster = unit_clusters[0]
                if unit_cluster.num_surrounding_units > (unit_cluster.num_send_blockers + 1):
                    # at least one unit remains in cluster.
                    allowed_to_block = True
                    unit_cluster.num_send_blockers += 1
            else:
                # unit is part of more thn one cluster
                allowed_to_block = True
                for uc in unit_clusters:
                    # leave no cluster behind:
                    if uc.num_surrounding_units <= (uc.num_send_blockers + 1):
                        # at least one unit remains in cluster.
                        allowed_to_block = False

                if allowed_to_block is True:
                    for uc in unit_clusters:
                        uc.num_send_blockers += 1

            return allowed_to_block

        for cluster in clusters_to_defence:
            cluster_units = set()
            # exclude o_units that are part of another cluster. We only block units that are coming to our cluster
            other_clusters = [oc for oc in self.cartographer.resource_clusters if oc != cluster]
            for o_unit in cluster.close_opponent_units:
                # check if opponent unit is part of another cluster:
                for oc in other_clusters:
                    if oc.unit_is_in_cluster(unit=o_unit):
                        cluster_units.add(o_unit)
            possible_invaders = [o_u for o_u in cluster.close_opponent_units if o_u not in cluster_units]

            for o_unit in possible_invaders:
                o_unit_dist, cluster_arrival_tile = Cartographer.distance_to_cluster(pos=(o_unit.pos.x, o_unit.pos.y),
                                                                                     cluster=cluster)
                o_unit_cell = self.cartographer.map.get_cell(o_unit.pos.x, o_unit.pos.y)
                arrival_cell = self.cartographer.map.get_cell(cluster_arrival_tile[0], cluster_arrival_tile[1])
                direction = o_unit_cell.pos.direction_to(arrival_cell.pos)
                adjacent_pos = o_unit_cell.pos.translate(direction, 1)
                # axis:
                if np.abs(o_unit.pos.x - cluster_arrival_tile[0]) >= np.abs(o_unit.pos.y - cluster_arrival_tile[1]):
                    moving_axis = "x"
                else:
                    moving_axis = "y"

                # try to find closest unit to block:
                min_dist = np.inf
                closest_unit = None
                for unit in self.free_units:
                    dist_to_o_unit = Cartographer.distance(origin=(unit.pos.x, unit.pos.y),
                                                           destination=(o_unit.pos.x, o_unit.pos.y))
                    dist_to_arrival_tile = Cartographer.distance(origin=(unit.pos.x, unit.pos.y),
                                                                 destination=(arrival_cell.pos.x, arrival_cell.pos.y))

                    if dist_to_arrival_tile < o_unit_dist:
                        if dist_to_o_unit < min_dist:
                            # check if unit is allowed to block
                            if unit_is_allowed_to_block(blocker_unit=unit):
                                min_dist = dist_to_o_unit
                                closest_unit = unit
                    elif dist_to_arrival_tile == o_unit_dist:
                        if (dist_to_o_unit < min_dist) and (unit.cooldown <= o_unit.cooldown):
                            # check if unit is allowed to block
                            if unit_is_allowed_to_block(blocker_unit=unit):
                                min_dist = dist_to_o_unit
                                closest_unit = unit

                if closest_unit is not None:
                    if min_dist == 1:
                        blocking_pos = (closest_unit.pos.x, closest_unit.pos.y)
                    else:
                        if moving_axis == "y":
                            if closest_unit.pos.x != o_unit.pos.x:
                                blocking_pos = (o_unit.pos.x, closest_unit.pos.y)
                            else:
                                blocking_pos = (adjacent_pos.x, adjacent_pos.y)
                        else:
                            if closest_unit.pos.y != o_unit.pos.y:
                                blocking_pos = (closest_unit.pos.x, o_unit.pos.y)
                            else:
                                blocking_pos = (adjacent_pos.x, adjacent_pos.y)
                    self.assign_order_to_unit(unit=closest_unit, position_tuple=blocking_pos,
                                              order_type=OrderType.Blocking)

    def execute_orders(self, game_state, show_annotation):
        """
        Executes orders. --> adds actions to actions.
        Note: We wont build 3 days before night if a city can't sustain by its own.
        :param game_state: global game_state
        :param show_annotation: boolean.
        """
        move_orders = []
        for order in self.orders:
            if order.dist == 0:
                if order.order_type == OrderType.Expansion:
                    # try to build:
                    if order.unit.can_act() and order.unit.can_build(game_state.map):
                        if order.additional_information.spot_collection_amount < 21:
                            # city can't be supported by its own. --> don't build 3 steps before night.
                            if self.steps_until_night > 3:
                                action = order.unit.build_city()
                                self.actions.append(action)
                        else:
                            action = order.unit.build_city()
                            self.actions.append(action)
            else:
                # move
                if order.unit.can_act():
                    move_orders.append(order)
        move_actions = self.movement_officer.move_units(move_orders=move_orders)

        for action in move_actions:
            self.actions.append(action)

        if show_annotation:
            self.order_annotation()

    def assign_order_to_unit(self, unit, position_tuple, order_type, additional_information=None):
        """
        Assigns an oder to a unit and thereby removes unit from free units.
        """
        if unit in self.free_units:
            self.orders.append(Order(order_type=order_type, unit=unit,
                                     pos=position_tuple, additional_information=additional_information))
            self.free_units.remove(unit)

    def order_annotation(self):
        for order in self.orders:
            if order.order_type == OrderType.Expansion:
                self.actions.append(annotate.circle(order.pos[0], order.pos[1]))
                self.actions.append(annotate.line(order.unit.pos.x, order.unit.pos.y, order.pos[0], order.pos[1]))
            elif order.order_type == OrderType.CitySupport:
                self.actions.append(annotate.x(order.pos[0], order.pos[1]))
                self.actions.append(annotate.line(order.unit.pos.x, order.unit.pos.y, order.pos[0], order.pos[1]))
                self.actions.append(annotate.text(order.unit.pos.x, order.unit.pos.y, "H", 15))
            elif order.order_type == OrderType.SaveSpot:
                self.actions.append(annotate.x(order.pos[0], order.pos[1]))
                self.actions.append(annotate.circle(order.pos[0], order.pos[1]))
                self.actions.append(annotate.line(order.unit.pos.x, order.unit.pos.y, order.pos[0], order.pos[1]))
            #elif order.order_type == OrderType.Distribution:
            #    self.actions.append(annotate.x(order.pos[0], order.pos[1]))
             #   self.actions.append(annotate.line(order.unit.pos.x, order.unit.pos.y, order.pos[0], order.pos[1]))
            elif order.order_type == OrderType.Blocking:
                self.actions.append(annotate.x(order.pos[0], order.pos[1]))
                self.actions.append(annotate.line(order.unit.pos.x, order.unit.pos.y, order.pos[0], order.pos[1]))

    def get_save_spots(self):
        """
        Builds a set of save spots. A Save spot is every tile on which a unit will survive the following night.
        This could be a city which will survive the following night or any other farming location.
        Note: Not all harvesting values are save. City tiles on a given harvesting spot can be dangerous.
        :return: set() or tuples
        """
        save_spots = set()
        for x in range(self.cartographer.width):
            for y in range(self.cartographer.height):
                if self.cartographer.city_map[x][y] == 0:
                    # no city tile
                    harvesting_tile = self.cartographer.harvesting_map[x][y]
                    if harvesting_tile.collection_amount_per_turn > 0 and self.cartographer.unit_map[x][y] < 2:
                        # no enemy is standing on this tile
                        save_spots.add(SaveSpot(pos=(x, y), is_city=False))
                elif self.cartographer.city_map[x][y] == 1:
                    # player city tile
                    city_id = self.cartographer.map.get_cell(x, y).citytile.cityid
                    district_mayor = self.city_council.get_district_mayor_by_id(city_id=city_id)
                    if district_mayor.survives_next_night:
                        save_spots.add(SaveSpot(pos=(x, y), is_city=True))
                else:
                    # opponent city tile. --> no save spot
                    pass
        return save_spots

    def order_save_spots(self):
        """
        Order all self.free_units to move to save location to survive the night.
        :return:
        """
        save_spots = self.get_save_spots()
        save_spot_order = []
        """
        Prefer save spots that are not wood harvesting spots: (We do not want to harvest wood if its not ordered)
        """
        priority_1_save_spots = []
        for spot in save_spots:
            if spot.is_city:
                if self.cartographer.harvesting_map[spot.pos[0]][spot.pos[1]].num_wood == 0:
                    # save spot without wood harvesting
                    priority_1_save_spots.append(spot)
            else:
                priority_1_save_spots.append(spot)

        priority_2_save_spots = [s for s in save_spots if s not in priority_1_save_spots]

        def save_spot_distribution(priority_save_spot: list):
            for unit in self.free_units:
                unit_cargo = 100 - unit.get_cargo_space_left()
                unit_will_die = unit_cargo < 40
                spot_positions = [spot.pos for spot in priority_save_spot]
                if (len(priority_save_spot) > 0) and unit_will_die:
                    if (unit.pos.x, unit.pos.y) not in spot_positions:
                        # find closes save spot for unit.
                        min_dist = np.inf
                        closest_spot = None
                        for spot in priority_save_spot:
                            dist = self.cartographer.distance(origin=(unit.pos.x, unit.pos.y), destination=spot.pos)
                            if dist < min_dist:
                                min_dist = dist
                                closest_spot = spot
                            elif (dist == min_dist) and (not spot.is_city):
                                # prefer non city save spots
                                min_dist = dist
                                closest_spot = spot

                        if closest_spot is not None:
                            unit_range = self.get_unit_range(unit=unit)
                            # in 6 steps a unit can move 3 tiles. (minimum)
                            if min_dist <= unit_range:
                                save_spot_order.append([unit, closest_spot])
                                if not closest_spot.is_city:
                                    # city save spots can host any number of units but other save spots only one.
                                    priority_save_spot.remove(closest_spot)
                    else:
                        # unit is standing on save spot.
                        if len(priority_save_spot) > 0:
                            closest_spot = [spot for spot in priority_save_spot
                                            if spot.pos == (unit.pos.x, unit.pos.y)][0]
                            save_spot_order.append([unit, closest_spot])
                            if not closest_spot.is_city:
                                # city save spots can host any number of units but other save spots only one.
                                priority_save_spot.remove(closest_spot)

        # fist priority 1 and then priority 2 save spots
        save_spot_distribution(priority_save_spot=priority_1_save_spots)
        save_spot_distribution(priority_save_spot=priority_2_save_spots)

        for order in save_spot_order:
            self.assign_order_to_unit(unit=order[0], position_tuple=order[1].pos,
                                      order_type=OrderType.SaveSpot)

    def order_city_support(self):
        def find_closes_free_unit_for_spot(district_harvesting_spot):
            """
            Finds the closest unit for given district_harvesting_spot.
            :param district_harvesting_spot: DistrictHarvestingSpot
            :return: closest_unit and its distance to the gives DistrictHarvestingSpot
            """
            m_dist = np.inf
            c_unit = None
            # only free units with less then 50 wood. (We do not want to wast wood.
            for unit in self.free_units:
                # if unit.cargo.wood < 50:
                dist = self.cartographer.distance(origin=district_harvesting_spot.pos,
                                                  destination=(unit.pos.x, unit.pos.y))
                if dist < m_dist:
                    m_dist = dist
                    c_unit = unit
                if m_dist == 0:
                    break
            return c_unit, m_dist

        for dist_mayor in self.city_council.district_mayors:
            if not dist_mayor.survives_next_night:
                for dist_ha_spot in dist_mayor.district_harvesting_spots:
                    if dist_ha_spot.harvesting_value > 27:
                        closest_unit, min_dist = find_closes_free_unit_for_spot(district_harvesting_spot=dist_ha_spot)
                        if closest_unit is not None and (min_dist < self.get_unit_range(unit=closest_unit)):
                            self.assign_order_to_unit(unit=closest_unit, position_tuple=dist_ha_spot.pos,
                                                      order_type=OrderType.CitySupport)

            else:
                # city will survive next night:
                for dist_ha_spot in dist_mayor.district_harvesting_spots:
                    if dist_ha_spot.includes_coal or dist_ha_spot.includes_uranium:
                        closest_unit, min_dist = find_closes_free_unit_for_spot(district_harvesting_spot=dist_ha_spot)
                        if closest_unit is not None and (min_dist < self.get_unit_range(unit=closest_unit)):
                            self.assign_order_to_unit(unit=closest_unit, position_tuple=dist_ha_spot.pos,
                                                      order_type=OrderType.CitySupport)

    def order_harvesting(self, units=None):
        if units is None:
            units = self.free_units

        def get_biggest_priority_city(unit):
            unit_day_range = math.floor(self.steps_until_night / 2)
            # find district in need with the highest priority within unit range
            max_priority = 0
            dist_to_max = np.inf
            max_priority_pos = None
            for district_mayor in district_mayors_for_farming:
                if district_mayor.harvesting_priority > 0:
                    dist, closest_tile_pos = Cartographer.distance_to_district(pos=(unit.pos.x, unit.pos.y),
                                                                               district_mayor=district_mayor)
                    if dist < unit_day_range:
                        """
                        Note: Unit range might be very high since the cargo is full.
                        """
                        if (district_mayor.harvesting_priority > max_priority) or \
                                ((district_mayor.harvesting_priority == max_priority) and (dist < dist_to_max)):
                            max_priority = district_mayor.harvesting_priority
                            dist_to_max = dist
                            max_priority_pos = closest_tile_pos
            return dist_to_max, max_priority_pos, max_priority

        # get all cities that need farming
        harvesting_orders = []
        district_mayors_for_farming = [district_mayor for district_mayor in self.city_council.district_mayors
                                       if not district_mayor.survives_all_nights]

        if self.night_steps_left < 12:
            # we harvest everything in the last day cycle:
            free_harvesting_positions = self.harvesting_officer.free_harvesting_positions
        else:
            free_harvesting_positions = self.harvesting_officer.strategic_harvesting_positions

        for unit in units:
            distance_to_city_tile, tile_pos, priority = get_biggest_priority_city(unit=unit)
            unit_day_range = math.floor(self.steps_until_night / 2)
            if (unit.get_cargo_space_left() == 0) or ((unit.get_cargo_space_left() <= 50) and
                                                      distance_to_city_tile < unit_day_range):
                # go to closest city in need.
                if tile_pos is not None:
                    harvesting_orders.append([unit, tile_pos, OrderType.Harvest_Return])

            else:
                unit_range = self.get_unit_range(unit=unit)
                # if not on harvesting spot move to closes spot.
                fuel_value_at_pos = self.cartographer.harvesting_map[unit.pos.x][unit.pos.y].fuel_value_per_turn
                if fuel_value_at_pos == 0:
                    # unit is not on a harvesting location --> find closest harvesting location:
                    min_dist = np.inf
                    closest_free_harvesting_pos = None
                    for free_pos in free_harvesting_positions:
                        dist = self.cartographer.distance(origin=[unit.pos.x, unit.pos.y],
                                                          destination=[free_pos[0], free_pos[1]])
                        if dist < min_dist:
                            min_dist = dist
                            closest_free_harvesting_pos = free_pos
                    if (closest_free_harvesting_pos is not None) and (unit_range >= min_dist):
                        # remove new position from free_harvesting_positions
                        free_harvesting_positions.remove(closest_free_harvesting_pos)
                        harvesting_orders.append([unit, closest_free_harvesting_pos, OrderType.Harvest_Go])
                else:
                    # look for better spot around.
                    directions = [[0, 1], [1, 0], [0, -1], [-1, 0]]
                    for d in directions:
                        new_x = unit.pos.x + d[0]
                        new_y = unit.pos.y + d[1]
                        max_fuel_value = 0
                        better_harvesting_pos = None
                        if (0 <= new_x < self.cartographer.width) and (0 <= new_y < self.cartographer.height):
                            fuel_value = self.cartographer.harvesting_map[new_x][new_y].fuel_value_per_turn
                            if ((new_x, new_y) in free_harvesting_positions) and fuel_value > max_fuel_value:
                                max_fuel_value = fuel_value
                                better_harvesting_pos = (new_x, new_y)
                        if (better_harvesting_pos is not None) and (max_fuel_value > fuel_value_at_pos):
                            # add old unit position to free_harvesting_positions and remove new position
                            free_harvesting_positions.add((unit.pos.x, unit.pos.y))
                            free_harvesting_positions.remove(better_harvesting_pos)
                            harvesting_orders.append([unit, better_harvesting_pos, OrderType.Harvest_Go])

        for order in harvesting_orders:
            self.assign_order_to_unit(unit=order[0], position_tuple=order[1], order_type=order[2])

    def order_expansions(self):
        """
        Order expansions until no worker is free.
        Runs a maximum of 10 cycles.
        :return:
        """
        counter = 1
        order_expansions = True
        full_cargo_units = [unit for unit in self.free_units if unit.get_cargo_space_left() == 0]
        if self.strategy_information.player_research_status > 1:
            self.order_closest_expansion_spots(units=full_cargo_units, max_number_per_unit=1)

        while order_expansions:
            counter += 1
            fastest_spots = self.order_fastest_expansion_spots()
            self.expansion_officer.update_expansion_maps(fastest_spots)
            for spot in fastest_spots:
                self.assign_order_to_unit(unit=spot.unit, position_tuple=spot.harvesting_pos,
                                          order_type=OrderType.Expansion, additional_information=spot)
            if (len(self.free_units) == 0) or (self.expansion_officer.get_number_of_free_expansion_spots() == 0)\
                    or counter == 10:
                order_expansions = False

    def order_closest_expansion_spots(self, units, max_number_per_unit=1):
        """
        Only for units with full cargo
        """
        for unit in units:
            unit_expansions = self.expansion_officer.find_strategic_expansions(unit=unit,
                                                                               max_number=max_number_per_unit)
            if len(unit_expansions) > 0:
                self.expansion_officer.update_expansion_maps(unit_expansions)
                self.assign_order_to_unit(unit=unit_expansions[0].unit, position_tuple=unit_expansions[0].harvesting_pos,
                                          order_type=OrderType.Expansion, additional_information=unit_expansions[0])

    def order_fastest_expansion_spots(self, max_number_per_unit=5):

        def get_closest_spot_to_opponent_unit(input_spots):
            closest_dist_to_enemy = np.inf
            best_spot = None
            for spot in input_spots:
                for unit in self.cartographer.opponent.units:
                    dist = Cartographer.distance(origin=spot.spot_pos,
                                                 destination=(unit.pos.x, unit.pos.y))
                    if dist < closest_dist_to_enemy:
                        closest_dist_to_enemy = dist
                        best_spot = spot
            return best_spot

        def get_closest_spot_to_next_expansion(input_spots, distribution_option):
            best_distribution_option = distribution_option.distribution_spots[0]
            closest_dist_to_distribution_spot = np.inf
            best_spots = []
            for spot in input_spots:
                dist = Cartographer.distance(
                    origin=spot.spot_pos, destination=(best_distribution_option.origin_tile_pos[0],
                                                       best_distribution_option.origin_tile_pos[1]))
                if dist < closest_dist_to_distribution_spot:
                    closest_dist_to_distribution_spot = dist
                    best_spots = [spot]
                elif dist == closest_dist_to_distribution_spot:
                    best_spots.append(spot)

            closest_spot_to_opponent = get_closest_spot_to_opponent_unit(input_spots)
            if closest_spot_to_opponent in best_spots:
                best_spot = closest_spot_to_opponent
            else:
                best_spot = best_spots[0]

            return best_spot


        expansion_options = []
        for unit in self.free_units:
            unit_expansions = self.expansion_officer.find_strategic_expansions(unit=unit,
                                                                               max_number=max_number_per_unit)
            expansion_options += unit_expansions

        # find best unit to build expansion.
        best_expansion_options = []
        unique_expansion_ids = set([ex_spot.id for ex_spot in expansion_options])
        for exp_id in unique_expansion_ids:
            spots_with_id = [spot for spot in expansion_options if spot.id == exp_id]
            min_time_to_build = min(spot.time_to_build for spot in spots_with_id)
            spots_with_fastest_building_time = [spot for spot in spots_with_id if
                                                spot.time_to_build == min_time_to_build]
            if len(spots_with_fastest_building_time) > 1:
                best_expansion_options += spots_with_fastest_building_time
            else:
                best_expansion_options.append(spots_with_fastest_building_time[0])

        # Now we have the best units for each expansion. Now we need to identify the best expansions since we probable
        # do not have the same amount of units as expansions.
        final_spots = []
        units = set([ex_spot.unit for ex_spot in best_expansion_options])
        for unit in units:
            # all spots where this specific unit is the fastest builder
            unit_spots = [spot for spot in best_expansion_options if unit == spot.unit]
            if len(unit_spots) > 0:
                # some unity may not have a fastest expansion spot since another unit took it.
                min_time_to_build = min(spot.time_to_build for spot in unit_spots) + 1  # min time + 1

                unit_spots_with_min_time = [spot for spot in unit_spots if spot.time_to_build <= min_time_to_build]

                # get unit_cluster:
                unit_clusters = set()
                for cluster in self.cartographer.resource_clusters:
                    dist, _ = Cartographer.distance_to_cluster(pos=(unit.pos.x, unit.pos.y), cluster=cluster)
                    if dist == 0:
                        unit_clusters.add(cluster)
                """
                NOTE: Here we decide how we choose between the best spots for a unit.
                      We prefer spots that are closer to enemy spots and sometime spots that are closer to next 
                      cluster positions.
                """
                if (len(unit_spots_with_min_time) > 1) and (min_time_to_build > 0):
                    if self.strategy_information.num_player_city_tiles == 1:
                        # get closest cluster
                        unit_cluster = None
                        if len(unit_clusters) > 0:
                            # choose the biggest wood cluster as unit cluster.
                            biggest_wood_cluster = None
                            max_num_wood_tiles = 0
                            for uc in unit_clusters:
                                if uc.num_wood_tiles > max_num_wood_tiles:
                                    max_num_wood_tiles = uc.num_wood_tiles
                                    biggest_wood_cluster = uc
                            if biggest_wood_cluster is not None:
                                unit_cluster = biggest_wood_cluster
                            else:
                                # one at random (shot not be possible i guess...)
                                unit_cluster = unit_clusters.pop()

                        if unit_cluster is not None:
                            distribution_option = self.get_distribution_options_for_cluster(cluster=unit_cluster)
                            if len(distribution_option.distribution_spots) > 0:
                                best_distribution_option = distribution_option.distribution_spots[0]
                                closest_dist_to_distribution_spot = np.inf
                                best_spots = []
                                for spot in unit_spots_with_min_time:
                                    dist = Cartographer.distance(
                                        origin=spot.spot_pos, destination=(best_distribution_option.origin_tile_pos[0],
                                                                           best_distribution_option.origin_tile_pos[1]))
                                    if dist < closest_dist_to_distribution_spot:
                                        closest_dist_to_distribution_spot = dist
                                        best_spots = [spot]
                                    elif dist == closest_dist_to_distribution_spot:
                                        best_spots.append(spot)
                                # check if closest spot is paar of min distance spots:
                                closest_spot_to_opponent = get_closest_spot_to_opponent_unit(unit_spots_with_min_time)
                                if closest_spot_to_opponent in best_spots:
                                    best_spot = closest_spot_to_opponent
                                else:
                                    best_spot = best_spots[0]
                            else:
                                # choose spot that is the closest to enemy unit:
                                best_spot = get_closest_spot_to_opponent_unit(unit_spots_with_min_time)
                        else:
                            # choose spot that is the closest to enemy unit:
                            best_spot = get_closest_spot_to_opponent_unit(unit_spots_with_min_time)
                    else:
                        # We have more then one captures cluster
                        # choose spot that is the closest to enemy unit:
                        best_spot = get_closest_spot_to_opponent_unit(unit_spots_with_min_time)
                else:
                    # only one spot, so len(unit_spots_with_min_time) = 1
                    if len(unit_spots_with_min_time) > 1:
                        print("WARNING: something went wrong for distribution spots. (General)")
                    best_spot = unit_spots_with_min_time[0]

                if best_spot is not None:
                    # check if unit can go there
                    unit_will_make_it = False
                    if self.day:
                        unit_range = self.get_unit_range(unit=best_spot.unit)
                        if unit_range >= best_spot.dist:
                            unit_will_make_it = True
                    else:
                        # move at night
                        if best_spot.dist == 1:
                            # unit is next to spot: (check if unit can survive at pos)
                            collection_amount = self.cartographer.harvesting_map[best_spot.spot_pos[0]][
                                best_spot.spot_pos[1]].collection_amount_per_turn
                            if collection_amount > 4:
                                unit_will_make_it = True
                        else:
                            # check if default direction leads to a farming cell.
                            cell = self.cartographer.map.get_cell(best_spot.spot_pos[0], best_spot.spot_pos[1])
                            direct_direction = best_spot.unit.pos.direction_to(cell.pos)
                            new_pos = best_spot.unit.pos.translate(direct_direction, 1)
                            collection_amount = self.cartographer.harvesting_map[new_pos.x][new_pos.y]. \
                                collection_amount_per_turn
                            if collection_amount > 4:
                                unit_will_make_it = True
                    if unit_will_make_it:
                        best_expansion_options = [exp_spot for exp_spot in best_expansion_options
                                                  if exp_spot.id != best_spot.id]
                        final_spots.append(best_spot)
        return final_spots

    def get_unit_range(self, unit):
        cargo = 100 - unit.get_cargo_space_left()
        if self.day:
            unit_range = math.floor(self.steps_until_night / 2) + math.floor(cargo / 16)
            # 16 = 4 * 4 (4 is cool down at night and 4 fuel per step --> 16 fuel per moved tile
        else:
            # night:
            unit_range = math.floor(cargo / 16)
        return unit_range

    def get_day_night_information(self, night_steps_left):
        """
        First of all we need to know in which state we are. In terms of night and day shift:
        There are 30 day steps followed by 10 night steps.
        """
        self.steps_until_night = 30 - self.cartographer.observation["step"] % 40
        if self.steps_until_night > 0:
            self.day = True
            self.steps_until_day = 0
        else:
            self.day = False
        """
        Count number of left night steps. This is important to calculate the amount of fuel for city tile.
        Is only updated during day time and therefor not perfectly granual.
        """
        if not self.day:
            night_steps_left -= 1
            self.steps_until_day = self.steps_until_night + 10
        self.night_steps_left = night_steps_left
        return night_steps_left

    def build_strategy_information(self):
        # Get city information:
        num_player_city_tiles = 0
        num_player_save_city_tiles = 0
        for dist_mayor in self.city_council.district_mayors:
            if dist_mayor.survives_all_nights:
                num_player_save_city_tiles += dist_mayor.size
            num_player_city_tiles += dist_mayor.size

        num_opponent_city_tiles = 0
        num_opponent_save_city_tiles = 0
        for city in self.cartographer.opponent.cities.values():
            city_size = len(city.citytiles)
            survives_all_nights = bool((city.get_light_upkeep() * self.night_steps_left) < city.fuel)
            if survives_all_nights:
                num_opponent_save_city_tiles += city_size
            num_opponent_city_tiles += city_size

        # Get research information:
        if self.cartographer.player.researched_uranium():
            player_research_status = 2
        elif self.cartographer.player.researched_coal():
            player_research_status = 1
        else:
            player_research_status = 0

        if self.cartographer.opponent.researched_uranium():
            opponent_research_status = 2
        elif self.cartographer.opponent.researched_coal():
            opponent_research_status = 1
        else:
            opponent_research_status = 0
        player_research_points = self.cartographer.player.research_points
        opponent_research_points = self.cartographer.opponent.research_points

        # Get map resource information (With Player Research):
        amount_of_wood_fuel = 0
        amount_of_coal_fuel = 0
        amount_of_uranium_fuel = 0

        for cluster in self.cartographer.resource_clusters:
            for resource_tile in cluster.resource_tiles:
                if resource_tile.resource_type == "w":
                    amount_of_wood_fuel += resource_tile.fuel_amount
                elif resource_tile.resource_type == "c":
                    amount_of_coal_fuel += resource_tile.fuel_amount
                elif resource_tile.resource_type == "u":
                    amount_of_uranium_fuel += resource_tile.fuel_amount

        step = self.cartographer.observation["step"]

        # get num player and opponent clusters:
        num_player_cluster = 0
        num_opponent_cluster = 0
        for cluster in self.cartographer.resource_clusters:
            if cluster.captured_by == "p":
                num_player_cluster += 1
            elif cluster.captured_by == "o":
                num_opponent_cluster += 1
            elif cluster.captured_by == "b":
                num_player_cluster += 1
                num_opponent_cluster += 1

        """
        Idea: We could think about the general resource information an the map. Independent of research.
              And the amount of cluster and there sice could also be key. 
        """

        strategy_information = StrategyInformation(num_player_city_tiles=num_player_city_tiles,
                                                   num_player_save_city_tiles=num_player_save_city_tiles,
                                                   num_opponent_city_tiles=num_opponent_city_tiles,
                                                   num_opponent_save_city_tiles=num_opponent_save_city_tiles,
                                                   player_research_status=player_research_status,
                                                   opponent_research_status=opponent_research_status,
                                                   player_research_points=player_research_points,
                                                   opponent_research_points=opponent_research_points,
                                                   amount_of_wood_fuel=amount_of_wood_fuel,
                                                   amount_of_coal_fuel=amount_of_coal_fuel,
                                                   amount_of_uranium_fuel=amount_of_uranium_fuel, step=step,
                                                   map_size=self.cartographer.map_size,
                                                   num_player_cluster=num_player_cluster,
                                                   num_opponent_cluster=num_opponent_cluster)
        self.strategy_information = strategy_information


class OrderType(Enum):
    Expansion = "Expansion"
    Harvest_Go = "Harvest_Go"
    Harvest_Return = "Harvest_Return"
    CitySupport = "CitySupport"
    SaveSpot = "SaveSpot"
    ClusterDefence = "ClusterDefence"
    Distribution = "Distribution"
    Blocking = "Blocking"


class Order:
    def __init__(self, order_type: OrderType, unit, pos, additional_information=None):
        """
        :param order_type: OrderType
        :param unit: lux unit
        :param pos: pos tuple
        """
        self.order_type = order_type
        self.unit = unit
        self.pos = pos
        self.additional_information = additional_information
        self.dist = Cartographer.distance(origin=(unit.pos.x, unit.pos.y), destination=pos)


class SaveSpot:
    def __init__(self, pos, is_city):
        self.pos = pos
        self.is_city = is_city


class StrategyInformation:
    def __init__(self, num_player_city_tiles, num_player_save_city_tiles, num_opponent_city_tiles, num_player_cluster,
                 num_opponent_cluster,
                 num_opponent_save_city_tiles, player_research_status, opponent_research_status, player_research_points,
                 opponent_research_points, amount_of_wood_fuel, amount_of_coal_fuel, amount_of_uranium_fuel, step,
                 map_size):
        self.num_player_city_tiles = num_player_city_tiles
        self.num_player_save_city_tiles = num_player_save_city_tiles
        self.num_player_cluster = num_player_cluster
        self.num_opponent_city_tiles = num_opponent_city_tiles
        self.num_opponent_save_city_tiles = num_opponent_save_city_tiles
        self.num_opponent_cluster = num_opponent_cluster
        self.player_research_status = player_research_status
        self.opponent_research_status = opponent_research_status
        self.player_research_points = player_research_points
        self.opponent_research_points = opponent_research_points
        self.amount_of_wood_fuel = amount_of_wood_fuel
        self.amount_of_coal_fuel = amount_of_coal_fuel
        self.amount_of_uranium_fuel = amount_of_uranium_fuel
        self.step = step
        self.map_size = map_size

    def show(self):
        print(50 * "-")
        print(f"Step: {self.step}  map_size: {self.map_size}")
        print(f"Fuel left: wood: {self.amount_of_wood_fuel}  |  coal: {self.amount_of_coal_fuel}"
              f"  |  uranium: {self.amount_of_uranium_fuel} ")
        print("           Player  |  Opponent")
        print(f"city_tiles      {self.num_player_city_tiles}  |  {self.num_opponent_city_tiles}")
        print(f"save_tiles      {self.num_player_save_city_tiles}  |  {self.num_opponent_save_city_tiles}")
        print(f"research state  {self.player_research_status}  |  {self.player_research_status}")
        print(f"research points {self.player_research_points}  |  {self.opponent_research_points}")
        print(f"num_player_cluster: {self.num_player_cluster}  |  {self.num_opponent_cluster}")
        print(50 * "-")


class DistributionSpot:
    def __init__(self, origin_cluster, other_cluster, dist, origin_tile_pos, destination_tile_pos):
        self.origin_cluster = origin_cluster
        self.other_cluster = other_cluster
        self.dist = dist
        self.origin_tile_pos = origin_tile_pos
        self.destination_tile_pos = destination_tile_pos
        self.priority = 0


class ClusterDistributionOptions:
    def __init__(self, cluster, units, strat_info, city_council):
        self.cluster = cluster
        self.cluster_units = []
        self.strategic_information = strat_info
        for unit in units:
            dist, _ = Cartographer.distance_to_cluster(pos=(unit.pos.x, unit.pos.y), cluster=cluster)
            if dist == 0:
                self.cluster_units.append(unit)
        self.distribution_spots = []
        # set num of units that could be send away
        """
        Note: If no enemy is around this number is all but one. If otherwise an enemy is around we need to make sure 
        that we can protect the cluster.
        --> We need one unit for each possible expansion spot and one for each city tiles that will not survive the
        next night.
        """
        self.max_num_distributions = 0
        if (cluster.captured_by == "b") or (cluster.captured_by == "p" and cluster.min_dist_to_opponent_unit < 6):
            # we do not want to lose captured clusters
            if strat_info.num_player_cluster == 1:
                if (len(cluster.attached_player_city_tiles_pos) == 2) and (cluster.num_surrounding_units == 2):
                    self.max_num_distributions = 1
                elif (len(cluster.attached_player_city_tiles_pos) == 3) and (cluster.num_surrounding_units > 2):
                    self.max_num_distributions = 2
                elif (len(cluster.attached_player_city_tiles_pos) == 4) and (cluster.num_surrounding_units > 2):
                    self.max_num_distributions = 2
            else:
                num_city_tiles_to_support = len(cluster.attached_player_city_tiles_pos)
                # exclude those that will survive the next night.
                for tile_pos in cluster.attached_player_city_tiles_pos:
                    district_major = city_council.get_district_mayor_by_pos(pos=tile_pos)
                    if district_major.survives_next_night:
                        num_city_tiles_to_support -= 1

                num_support_tiles = num_city_tiles_to_support + cluster.num_possible_expansions
                if cluster.num_surrounding_units > num_support_tiles:
                    self.max_num_distributions = cluster.num_surrounding_units - num_support_tiles
                else:
                    if cluster.num_surrounding_units >= (cluster.num_surrounding_opponent_units + 2):
                        self.max_num_distributions = cluster.num_surrounding_units - \
                                                     (cluster.num_surrounding_opponent_units + 2)
        else:
            if (len(cluster.attached_player_city_tiles_pos) == 2) and (cluster.num_surrounding_units == 2):
                self.max_num_distributions = 1
            elif (len(cluster.attached_player_city_tiles_pos) == 3) and (cluster.num_surrounding_units > 2):
                self.max_num_distributions = 2
            elif (len(cluster.attached_player_city_tiles_pos) >= 3) and (cluster.num_surrounding_units > 2):
                self.max_num_distributions = 2
        self.num_usable_units = self.max_num_distributions

    def add_spot(self, spot: DistributionSpot):
        self.distribution_spots.append(spot)

    def prioritize_spots(self):
        """
        Adds the priority to each spot in self.distribution_spots and then sorts all spots recording to there priority.
        """
        for spot in self.distribution_spots:
            if (spot.other_cluster.num_surrounding_units < 1) \
                    and (len(spot.other_cluster.attached_player_city_tiles_pos) == 0):
                base_priority = spot.other_cluster.num_wood_tiles
                priority = base_priority
                # only if we have no unit there we want to co there.
                # check for territory
                if self.strategic_information.num_player_cluster == 1:
                    # we do not want the player to walk to the opponent cluster first.
                    if spot.other_cluster.territory == "o":
                        priority = 0
                else:
                    # even if we do hae more then one cluster we should still prefer expand on our side of the map first
                    if spot.other_cluster.territory == "o":
                        priority = base_priority * 0.6

                if spot.other_cluster.territory == "b":
                    # We should highly prioritise both clusters.
                    priority = base_priority * 1.51
                """
                Note: Increasing priority fpr clusters with coal or uranium did't work out in the early games.
                """
                spot.priority = priority
        self.distribution_spots = sorted(sorted(self.distribution_spots,
                                                key=lambda k: k.dist), key=lambda k: k.priority, reverse=True)

    def trim_spots(self):
        """
        One cluster can only afford a certain amount of distributions spots. Drop all but the best
        self.max_num_distributions spots.
        """
        self.distribution_spots = [spot for spot in self.distribution_spots if spot.priority > 0]
        self.distribution_spots = self.distribution_spots[:max(self.max_num_distributions, 2)]


class HarvestingOfficer:
    def __init__(self, harvesting_map, resource_clusters, lux_map):
        self.map = lux_map
        self.height = lux_map.height
        self.width = lux_map.width
        self.harvesting_map = harvesting_map
        self.resource_clusters = resource_clusters
        self.free_harvesting_positions = self.get_free_harvesting_positions()
        self.strategic_harvesting_positions = self.get_strategic_harvesting_positions()

    def get_free_harvesting_positions(self):
        """
        Get's all free harvesting locations as set.
        :return: set of position tuples.
        """
        free_harvesting_tiles = set()
        for x in range(self.width):
            for y in range(self.height):
                if self.harvesting_map[x][y].fuel_value_per_turn > 0:
                    free_harvesting_tiles.add((x, y))
        return free_harvesting_tiles

    def get_strategic_harvesting_positions(self):
        strategic_harvesting_positions = self.free_harvesting_positions.copy()
        # exclude wood tiles that are within players control.
        for cluster in self.resource_clusters:
            if cluster.captured_by == "p":
                possible_farming_tiles = [rt.pos for rt in cluster.resource_tiles] + \
                                         [st for st in cluster.surrounding_tiles_pos
                                          if st not in cluster.attached_player_city_tiles_pos]

                for tile_pos in possible_farming_tiles:
                    harvesting_tile = self.harvesting_map[tile_pos[0]][tile_pos[1]]
                    if harvesting_tile.num_wood > 0:
                        directions = [[0, 1], [1, 0], [0, -1], [-1, 0], [0, 0]]
                        # check if we wood kill wood tile:
                        is_harvesting_spot = True
                        for d in directions:
                            new_x = tile_pos[0] + d[0]
                            new_y = tile_pos[1] + d[1]
                            if (0 <= new_x < self.width) and (0 <= new_y < self.height):
                                cell = self.map.get_cell(new_x, new_y)
                                if cell.has_resource():
                                    if cell.resource.type == Constants.RESOURCE_TYPES.WOOD:
                                        if cell.resource.amount < 200:
                                            is_harvesting_spot = False
                                            break
                        if (not is_harvesting_spot) and (tile_pos in strategic_harvesting_positions):
                            strategic_harvesting_positions.remove(tile_pos)

        return strategic_harvesting_positions

game_state = None

def agent(observation, configuration):
    global game_state
    global night_steps_left
    global territory_map

    step_start = time.time()

    if observation["step"] == 0:
        game_state = Game()
        game_state._initialize(observation["updates"])
        game_state._update(observation["updates"][2:])
        game_state.id = observation.player
    else:
        game_state._update(observation["updates"])

    actions = []

    player = game_state.players[observation.player]
    opponent = game_state.players[(observation.player + 1) % 2]

    if observation["step"] == 0:
        """
        Set some initial variables:
        """
        night_steps_left = 90
        cartographer = Cartographer(lux_map=game_state.map, player=player, opponent=opponent, observation=observation)
        territory_map = cartographer.build_territory_map()

    cartographer = Cartographer(lux_map=game_state.map, player=player, opponent=opponent, observation=observation)
    cartographer.territory_map = territory_map
    cartographer.map_battlefield()
    cartographer.build_resource_cluster()
    harvesting_officer = HarvestingOfficer(harvesting_map=cartographer.harvesting_map,
                                           resource_clusters=cartographer.resource_clusters, lux_map=game_state.map)
    movement_officer = MovementOfficer(step=observation["step"], city_map=cartographer.city_map,
                                       unit_map=cartographer.unit_map, player=player,
                                       opponent=opponent, lux_map=game_state.map,
                                       harvesting_map=cartographer.harvesting_map)
    expansion_officer = ExpansionOfficer(lux_map=game_state.map, city_map=cartographer.city_map,
                                         harvesting_grid=cartographer.harvesting_map,
                                         builder_obstacles_map=movement_officer.builder_obstacles_map,
                                         obstacles_map=movement_officer.obstacles_map,
                                         resource_cluster=cartographer.resource_clusters,
                                         movement_officer=movement_officer)
    city_council = CityCouncil(lux_map=game_state.map, city_map=cartographer.city_map, unit_map=cartographer.unit_map,
                               player=player, harvesting_map=cartographer.harvesting_map,
                               expansion_officer=expansion_officer)
    general = General(cartographer=cartographer, expansion_officer=expansion_officer, movement_officer=movement_officer,
                      city_council=city_council, harvesting_officer=harvesting_officer, actions=actions)
    night_steps_left = general.get_day_night_information(night_steps_left=night_steps_left)
    movement_officer.day = general.day
    city_council.summon_district_mayors(night_steps_left=general.night_steps_left)
    expansion_officer.district_mayors = city_council.district_mayors
    general.build_strategy_information()
    expansion_officer.build_expansion_maps(strategy_information=general.strategy_information, units=general.free_units)
    general.order()
    movement_officer.build_movement_map(orders=general.orders)
    general.execute_orders(game_state=game_state, show_annotation=False)

    return actions
