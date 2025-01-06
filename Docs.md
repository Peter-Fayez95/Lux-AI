# Lux AI Challenge Bot Logic Documentation

This document provides a detailed explanation of the bot's logic, focusing on the main controllers and their functionalities. The bot is designed to manage resources, units, and missions efficiently to maximize resource collection and city development.

---

## **1. Agent Controller**

The `agent` function is the core of the bot. It processes the game state, updates clusters, assigns missions, and issues actions for units and city tiles.

### **Key Responsibilities**
- **Initialization**: Initializes the game state and clusters at the start of the game.
- **Resource Collection**: Identifies and collects resources on the map.
- **Cluster Updates**: Updates clusters and assigns missions to units.
- **Action Issuance**: Issues actions for units and city tiles based on the current game state.

### **Workflow**
1. **Initialization**:
   - At the start of the game (`observation["step"] == 0`), the game state and clusters are initialized.
   - The `ClusterController` is initialized, and clusters are identified using a Depth-First Search (DFS) approach.

2. **Resource Collection**:
   - The bot retrieves all resource cells on the map using `get_resources`.
   - It filters minable resources based on the player's research level using `get_minable_resource_cells`.

3. **Cluster Updates**:
   - Clusters are updated based on the current game state using `cluster_controller.update_clusters`.
   - Units without clusters are identified and assigned to clusters using `cluster_controller.assign_worker`.

4. **Mission Assignment**:
   - Missions are assigned to units based on the cluster's needs (e.g., building, guarding, exploring).
   - Target positions are assigned to missions using `cluster.assign_targets_to_missions`.

5. **Action Issuance**:
   - Build actions are issued for units using `cluster.get_build_actions`.
   - Required moves for units are calculated using `cluster.get_required_moves`.
   - Actions for city tiles (e.g., building workers, researching) are issued using `get_city_actions`.

---

## **2. Cluster Controller**

The `ClusterController` class manages resource clusters, which are groups of connected resource cells. It uses a Disjoint Set Union (DSU) data structure to efficiently manage clusters.

### **Key Responsibilities**
- **Cluster Initialization**: Identifies clusters using DFS and initializes them.
- **Cluster Updates**: Updates clusters based on the current game state.
- **Worker Assignment**: Assigns workers to clusters based on a scoring system.
- **Unit Management**: Tracks units assigned to clusters.

### **Key Functions**
1. **`getClustersRolling`**:
   - Uses DFS to identify clusters of connected resource cells.
   - Initializes clusters and stores them in `clusterDict`.

2. **`update_clusters`**:
   - Updates resource cells, units, and perimeters for each cluster.
   - Removes consumed resources and dead units.

3. **`assign_worker`**:
   - Assigns workers to clusters based on a scoring system that considers distance, resource cells, perimeter, and opponent presence.

4. **`get_units_without_clusters`**:
   - Identifies units that are not assigned to any cluster.

### **Key Variables**
- **`clusterDict`**: Dictionary mapping cluster IDs to `Cluster` objects.
- **`woodClusters`, `coalClusters`, `uraniumClusters`**: Lists of clusters for each resource type.

---

## **3. Mission Controller**

The `Mission` class represents a task assigned to a unit, such as building, guarding, or exploring. The `Cluster` class manages missions for each cluster.

### **Key Responsibilities**
- **Mission Assignment**: Assigns missions to units based on cluster needs.
- **Target Assignment**: Assigns target positions to missions.
- **Mission Execution**: Issues actions for missions (e.g., building, moving).

### **Key Functions**
1. **`assign_targets_to_missions`**:
   - Assigns target positions to missions based on mission type (e.g., building, guarding, exploring).

2. **`get_build_actions`**:
   - Issues build actions for units that are at their target positions and have enough resources.

3. **`get_required_moves`**:
   - Calculates required moves for units to reach their target positions.

4. **`handle_explore_missions`**:
   - Manages explore missions, ensuring units have enough fuel to survive the night.

### **Key Variables**
- **`missions`**: List of missions for the cluster.
- **`target_pos`**: Target position for the mission.
- **`responsible_unit`**: Unit responsible for the mission.

---

## **4. Resource Controller**

The `resourceService` module provides functions to manage resources on the map.

### **Key Responsibilities**
- **Resource Identification**: Retrieves all resource cells on the map.
- **Resource Filtering**: Filters minable resources based on the player's research level.

### **Key Functions**
1. **`get_resources`**:
   - Retrieves all resource cells on the map.

2. **`get_minable_resource_cells`**:
   - Filters resource cells that can be mined by the player based on their research level.

3. **`get_resources_from_cells`**:
   - Retrieves resource cells from a list of positions.

### **Key Variables**
- **`resource_cells`**: List of resource cells on the map.

---

## **5. Unit Controller**

The `unitsService` module provides functions to manage units.

### **Key Responsibilities**
- **Unit Retrieval**: Retrieves units by their ID.
- **Cargo Management**: Calculates the remaining cargo space for a unit.
- **Action Validation**: Checks if a unit can perform an action.

### **Key Functions**
1. **`get_unit_by_id`**:
   - Retrieves a unit by its ID.

2. **`get_cargo_space_left`**:
   - Calculates the remaining cargo space for a unit.

3. **`can_act`**:
   - Checks if a unit can perform an action.

### **Key Variables**
- **`units`**: List of units controlled by the player.

---

## **6. City Controller**

The `helperFunctions` module provides functions to manage city tiles and their actions.

### **Key Responsibilities**
- **City Tile Actions**: Issues actions for city tiles, such as building workers and researching.
- **City Tile Scoring**: Calculates a score for city tiles to determine the best action.

### **Key Functions**
1. **`get_city_actions`**:
   - Issues actions for city tiles, such as building workers and researching.

2. **`get_citytile_score`**:
   - Calculates a score for city tiles based on resource availability, perimeter, and opponent presence.

### **Key Variables**
- **`citytiles`**: List of city tiles controlled by the player.