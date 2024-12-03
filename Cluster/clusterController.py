import logging
import math

# from typing import List, Dict, Tuple
from Cluster.Cluster import Cluster
# from agent import game_state
from lux.game_map import Cell

from helperFunctions.helper_functions import (inside_map,
    get_cell_neighbours_eight, same_resource)

logging.basicConfig(filename="ClusterController.log", level=logging.INFO)


class ClusterController:
    '''
    This Class is a DSU Data Structure for Clusters

    parent:         List(List(int))         Cluster Representative of each Cell Cluster
    rank:           List(int)               Cell Rank (for finding Cluster Rep.)
    clustersDict:   Dict[int -> Cluster]    Mapping of Each Cluster Representative to Cluster
    '''

    def __init__(self, width, height, gamestate):
        self.width = width
        self.height = height
        
        self.parent = []
        for x in range(width):
            for y in range(height):
                 self.parent.append(self.get_cell_value(x, y))
        
        self.rank = [0 for i in range(width * height)]
        self.clusterDict = dict()
        self.woodClusters = []
        self.coalClusters = []
        self.uraniumClusters = []
        # logging.info("ClusterController Started")

    def get_cell_value(self, x: int, y: int):
            return x * self.width + y

    # This method is only called once (at the game start)
    def getClustersRolling(self, width, height, game_state):
        # logging.info("Getting Clusters Rolling")
        # print("Getting Clusters Rolling")
        visited_cell = [[False for _ in range(height)] for _ in range(width)]


        def dfs(x, y, cluster_cells, gamestate):
            visited_cell[x][y] = True
            real_cell = game_state.map.get_cell(x, y)
            cluster_cells.append(real_cell)

            for cell in get_cell_neighbours_eight(Cell(x, y), gamestate):
                if not visited_cell[cell.pos.x][cell.pos.y]:
                    neighbour_cell = game_state.map.get_cell(cell.pos.x, cell.pos.y)

                    if neighbour_cell.has_resource() and same_resource(real_cell, neighbour_cell):
                        dfs(neighbour_cell.pos.x, neighbour_cell.pos.y, cluster_cells, gamestate)

        

        for x in range(width):
            for y in range(height):
                cell = game_state.map.get_cell(x, y)
                
                if cell.has_resource() and not visited_cell[x][y]:
                    cluster_cells = []
                    
                    # logging.info(f"This cell has resources: {cell}")
                    
                    # Start DFS for this cluster
                    dfs(x, y, cluster_cells, game_state)
                    
                    # Union all cells found in this cluster
                    for i in range(1, len(cluster_cells)):
                        self.unionClusters(cluster_cells[0], cluster_cells[i])

                    current_cluster = Cluster(cell.resource.type, self.rank[self.get_cell_value(x, y)], cluster_cells)
                    if cell.resource.type == "wood":
                        self.woodClusters.append(current_cluster)
                    elif cell.resource.type == "coal":
                        self.coalClusters.append(current_cluster)
                    else:
                        self.uraniumClusters.append(current_cluster)

                    self.clusterDict[self.get_cell_value(x, y)] = current_cluster


    
    # find unique Cluster by its representative cell
    def findCluster(self, cell):
        cell_value = self.get_cell_value(cell.pos.x, cell.pos.y)
        
        if self.parent[cell_value] != cell_value:
            # Convert the parent index back to x, y coordinates to call findCluster recursively
            parent_x = self.parent[cell_value] // self.width
            parent_y = self.parent[cell_value] % self.width
            # Recursively call findCluster and apply path compression
            self.parent[cell_value] = self.findCluster(Cell(parent_x, parent_y))
        
        return self.parent[cell_value]

        
    # Check if two cells belong to the same cluster
    def isSameCluster(self, cell1: Cell, cell2: Cell):
        # logging.info("cell from isSameCluster:", cell1, cell2)
        return self.findCluster(cell1) == self.findCluster(cell2)
    
    # Union two Clusters
    def unionClusters(self, cell1: Cell, cell2: Cell):
        # logging.info("cell from unionClusters:", cell1, cell2)
        if self.isSameCluster(cell1, cell2):
            return
        
        # Find the Cluster Representative of each cell
        ClusterRep1 = self.findCluster(cell1)
        ClusterRep2 = self.findCluster(cell2)

        if self.rank[ClusterRep1] > self.rank[ClusterRep2]:
            ClusterRep1, ClusterRep2 = ClusterRep2, ClusterRep1

        self.parent[ClusterRep1] = self.parent[ClusterRep2]

        if self.rank[ClusterRep1] == self.rank[ClusterRep2]:
            self.rank[ClusterRep2] += 1

    def update_clusters(self, game_state, player):
        for Clusterid, cluster in self.clusterDict.items():
            cluster.update_cluster(game_state, player)

    def update_missions(self, game_state, player):
        # logging.debug(f"Updating Missions for Step {step}")
        # print(f"Updating Missions for Step {step}")
        for Clusterid, cluster in self.clusterDict.items():
            cluster.update_missions(game_state, player)


    def assign_worker(self, worker, game_state, player, player_id, opponent):
        # Scores[Int -> Score]
        # For Each cluster represented by id, get its score for this worker

        copyDict = self.clusterDict.copy()

        for id, cluster in self.clusterDict.items():
            if not player.researched_coal() and cluster.resource_type == "coal":
                del copyDict[id]
            if not player.researched_uranium() and cluster.resource_type == "uranium":
                del copyDict[id]

        maximum_score = -math.inf
        assigned_cluster = None

        for id, cluster in copyDict.items():
            current_cluster_score = cluster.get_cluster_score_for_worker(worker, game_state, player_id, opponent)

            if current_cluster_score > maximum_score:
                maximum_score = current_cluster_score
                assigned_cluster = cluster

        return assigned_cluster
    
    def get_units_without_clusters(self, player):
        units_with_clusters = []
        for id, cluster in self.clusterDict.items():
            units_with_clusters.extend(cluster.units)

        units_without_clusters = []
        for unit in player.units:
            if unit.id not in units_with_clusters:
                units_without_clusters.append(unit)

        return units_without_clusters
