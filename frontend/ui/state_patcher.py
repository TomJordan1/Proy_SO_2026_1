import copy

def apply_delta(base_state: dict, updates: dict) -> dict:
    """
    Applies a delta (updates) to a base state and returns the patched state.
    Modifies base_state IN PLACE for efficiency. Make sure to deepcopy before calling if needed.
    """
    for key, value in updates.items():
        if isinstance(value, list) and key in ("process_table", "cores", "io_devices"):
            if key not in base_state:
                base_state[key] = []
            
            id_field = "pid" if key == "process_table" else "id" if key == "cores" else "name"
            
            # Map existing objects
            id_map = {obj.get(id_field): i for i, obj in enumerate(base_state[key]) if id_field in obj}
            
            for update_obj in value:
                obj_id = update_obj.get(id_field)
                if obj_id in id_map:
                    # Update existing object
                    base_state[key][id_map[obj_id]].update(update_obj)
                else:
                    # Add new object
                    base_state[key].append(update_obj)
                    id_map[obj_id] = len(base_state[key]) - 1
        elif isinstance(value, dict) and key in base_state and isinstance(base_state[key], dict):
            # Recursively update dictionary (like memory or metrics)
            # Actually, the backend replaces memory and metrics completely if they change,
            # but doing an update is safer.
            base_state[key].update(value)
        else:
            # Replace entirely
            base_state[key] = value
            
    return base_state

def get_state_at_tick(playback_data: list, target_tick_index: int, static_info: dict) -> dict:
    """
    Reconstructs the full state at target_tick_index using Snapshots and Deltas.
    playback_data is the array of ticks from output.json.
    """
    if not playback_data:
        return {}
        
    target_tick_index = max(0, min(target_tick_index, len(playback_data) - 1))
    
    # 1. Find the nearest snapshot backwards
    snapshot_idx = target_tick_index
    while snapshot_idx >= 0:
        if playback_data[snapshot_idx].get("type") == "snapshot":
            break
        # Legacy support (all ticks are snapshots)
        if "type" not in playback_data[snapshot_idx]:
            break
        snapshot_idx -= 1
        
    if snapshot_idx < 0:
        # Fallback if no snapshot found
        snapshot_idx = 0
        
    # 2. Clone the snapshot state
    frame = playback_data[snapshot_idx]
    base_state = copy.deepcopy(frame.get("state", frame))
    
    # 3. Apply deltas
    for i in range(snapshot_idx + 1, target_tick_index + 1):
        frame = playback_data[i]
        if frame.get("type") == "delta":
            apply_delta(base_state, frame.get("updates", {}))
        elif frame.get("type") == "snapshot":
            base_state = copy.deepcopy(frame.get("state", frame))
        else:
            # Legacy support
            base_state = copy.deepcopy(frame)
            
    # 4. Inject static info into process_table and ready_queues
    if "process_table" in base_state:
        for p in base_state["process_table"]:
            if p.get("pid") in static_info:
                p.update(static_info[p["pid"]])
                
    if "ready_queues" in base_state:
        for q in base_state["ready_queues"]:
            for p in q:
                if p.get("pid") in static_info:
                    p.update(static_info[p["pid"]])
                    
    if "waiting" in base_state:
        for p in base_state["waiting"]:
            if p.get("pid") in static_info:
                p.update(static_info[p["pid"]])
                
    # Add the tick number and console logs for the target tick
    base_state["tick"] = playback_data[target_tick_index].get("tick", 0)
    base_state["console_logs"] = playback_data[target_tick_index].get("console_logs", [])
    
    return base_state
