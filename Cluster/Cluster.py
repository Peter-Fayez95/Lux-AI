

class Cluster:
    '''
    The cluster is basically a connected component of resources
    Each cluster consists of only one type of resources (Wood / Coal / Uranium)

    clusterID       int             Representative Cell DSU Rank
    cells           List(Cells)     List of this cluster's cells
    '''
    def __init__(self, cluster_id, cells):
        self.clusterID = cluster_id
        self.cells = cells