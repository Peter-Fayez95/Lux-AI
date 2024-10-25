import logging

from Cluster.Cluster import Cluster
from lux.game_map import Cell

from helper_functions import inside_map, get_cell_neighbours_eight


logging.basicConfig(filename="ClusterController.log", level=logging.INFO)




class ClusterController:
    '''
    This Class is a DSU Data Structure for Clusters

    parent:         List(List(Cell))        Cluster Representative of each Cell Cluster
    rank:           List(List(int))         Cell Rank (for finding Cluster Rep.)
    clustersDict:   Dict[int -> Cluster]    Mapping of Each Cluster Representative to Cluster

    TODO: Add Cluster Updates
    '''

    def __init__(self, width, height):
        self.parent = [[Cell(x, y) for y in range(height)] for x in range(width)]
        self.rank = [[0 for _ in range(height)] for _ in range(width)]
        self.clusterDict = dict()
        logging.info("ClusterController Started")


    # This method is only called once (at the game start)
    def getClustersRolling(self, width, height, game_state):
        visited_cell = [[False for _ in range(height)] for _ in range(width)]


        def dfs(x, y, cluster_cells, gamestate):
            visited_cell[x][y] = True
            cluster_cells.append(Cell(x, y))

            for cell in get_cell_neighbours_eight(Cell(x, y), gamestate):
                if not visited_cell[cell.pos.x][cell.pos.y]:
                    neighbour_cell = game_state.map.get_cell(cell.pos.x, cell.pos.y)

                    if neighbour_cell.has_resource():
                        dfs(neighbour_cell.pos.x, neighbour_cell.pos.y, cluster_cells, gamestate)

        

        for x in range(width):
            for y in range(height):
                cell = game_state.map.get_cell(x, y)
                
                if cell.has_resource() and not visited_cell[x][y]:
                    cluster_cells = []
                    
                    logging.info(f"This cell has resources: {cell}")
                    
                    # Start DFS for this cluster
                    dfs(x, y, cluster_cells, game_state)
                    
                    # Union all cells found in this cluster
                    for i in range(1, len(cluster_cells)):
                        self.unionClusters(cluster_cells[0], cluster_cells[i])

                    current_cluster = Cluster(self.rank[x][y], cluster_cells)
                    self.clusterDict[self.rank[x][y]] = current_cluster




    
    # find unique Cluster by its representative cell
    def findCluster(self, cell: Cell):
        # logging.info("cell from findCluster:", cell)
        if self.parent[cell.pos.x][cell.pos.y] == cell:
            return cell
        
        else:
            self.parent[cell.pos.x][cell.pos.y] = self.findCluster(self.parent[cell.pos.x][cell.pos.y])
            return self.parent[cell.pos.x][cell.pos.y]
        
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

        if [ClusterRep1.pos.x, ClusterRep1.pos.y] > [ClusterRep2.pos.x, ClusterRep2.pos.y]:
            ClusterRep1, ClusterRep2 = ClusterRep2, ClusterRep1

        self.parent[ClusterRep1.pos.x][ClusterRep1.pos.y] = self.parent[ClusterRep2.pos.x][ClusterRep2.pos.y]

        if self.rank[ClusterRep1.pos.x][ClusterRep1.pos.y] == self.rank[ClusterRep2.pos.x][ClusterRep2.pos.y]:
            self.rank[ClusterRep2.pos.x][ClusterRep2.pos.y] += 1

        