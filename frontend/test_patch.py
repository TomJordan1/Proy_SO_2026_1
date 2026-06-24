import json
import sys
from ui.state_patcher import get_state_at_tick

def run():
    print("Loading JSON...")
    with open("../shared_data/output.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    print("Parsing global process info...")
    static_info = {p["pid"]: p for p in data.get("global_process_info", [])}
    ticks = data.get("ticks", [])
    
    print(f"Loaded {len(ticks)} ticks.")
    
    # Test getting state at tick 50
    state_50 = get_state_at_tick(ticks, 50, static_info)
    print(f"State at tick 50 generated: {state_50.get('tick')}")
    
    # Test getting state at tick 1999
    state_1999 = get_state_at_tick(ticks, 1999, static_info)
    print(f"State at tick 1999 generated: {state_1999.get('tick')}")

    # Verify metrics matches
    print(f"Metrics at 1999: {state_1999.get('metrics')}")

if __name__ == "__main__":
    run()
