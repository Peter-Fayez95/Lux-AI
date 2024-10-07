import Cluster
from lux.game_map import Cell


class ClusterController:
    
    '''
    This Cluster Controller is a DSU Data Structure for Clusters

    parent:         List(List(Cell))        Cluster Representative of each Cell Cluster
    rank:           List(List(int))         Cell Rank (for finding Cluster Rep.)
    clusterSize:    List(List(int))         Cluster Size for this Cell's Cluster
    numClusters:    int                     number of Resource Clusters              
    '''

    def __init__(self, width, height, resourceTiles):
        self.parent = [[[Cell(0, 0)] for _ in range(height)] for _ in range(width)]
        self.rank = [[0 for _ in range(height)] for _ in range(width)]
        self.clusterSize = [[1 for _ in range(height)] for _ in range(width)]
        
        # Initialize Cell Parents
        for x in range(width):
            for y in range(height):

                # The Cell parent is itself
                self.parent[x][y] = Cell(x, y)
    
        self.numClusters = len(resourceTiles)
    
    # find unique Cluster by its representative cell
    def findCluster(self, cell: Cell):
        if self.parent[cell.x][cell.y] == cell:
            return cell
        
        else:
            self.parent[cell.x][cell.y] = self.findCluster(self.parent[cell.x][cell.y])
            return self.parent[cell.x][cell.y]
        
    # Check if two cells belong to the same cluster
    def isSameCluster(self, cell1: Cell, cell2: Cell):
        return self.findCluster(cell1) == self.findCluster(cell2)
    
    def getNumberOfClusters(self):
        return self.numClusters
    
    # Union two Clusters
    def unionClusters(self, cell1: Cell, cell2: Cell):
        if self.isSameCluster(cell1, cell2):
            return
        
        # Find the Cluster Representative of each cell
        ClusterRep1 = self.findCluster(cell1), ClusterRep2 = self.findCluster(cell2)

        if ClusterRep1 > ClusterRep2:
            ClusterRep1, ClusterRep2 = ClusterRep2, ClusterRep1

        self.parent[ClusterRep1.x][ClusterRep1.y] = self.parent[ClusterRep2.x][ClusterRep2.y]

        if self.rank[ClusterRep1.x][ClusterRep1.y] == self.rank[ClusterRep2.x][ClusterRep2.y]:
            self.rank[ClusterRep2.x][ClusterRep2.y] += 1
        
        self.clusterSize[ClusterRep2.x][ClusterRep2.y] += self.clusterSize[ClusterRep1.x][ClusterRep1.y]

        self.numClusters -= 1