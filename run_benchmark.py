import json
import subprocess
import os
import sys

base_dir = r"C:\Users\tomjo\Dev\Proy_SO_2026_1"
input_path = os.path.join(base_dir, "shared_data", "input.json")
output_path = os.path.join(base_dir, "shared_data", "output.json")
simulator_exe = os.path.join(base_dir, "backend", "simulator.exe")

def run_sim(scheduler, mem_strategy):
    with open(input_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    config['hardware']['cpu']['scheduler'] = scheduler
    config['hardware']['memory']['allocationStrategy'] = mem_strategy
    # Remove KEYBOARD events to prevent waiting if any
    config['events'] = []
    
    with open(input_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
        
    subprocess.run([simulator_exe, "-i", input_path, "-o", output_path, "-t", "5000", "-b"], capture_output=True)
    
    with open(output_path, 'r', encoding='utf-8') as f:
        out_data = json.load(f)
    
    last_metrics = {}
    max_frag = 0.0
    for tick_data in reversed(out_data['ticks']):
        if 'updates' in tick_data:
            upd = tick_data['updates']
            if 'metrics' in upd and not last_metrics:
                last_metrics = upd['metrics']
            if 'memory' in upd and 'stats' in upd['memory']:
                frag = upd['memory']['stats'].get('fragmentation_percent', 0)
                if frag > max_frag:
                    max_frag = frag
                    
    last_metrics['max_fragmentation'] = max_frag
    return last_metrics

print("--- CPU Schedulers (Memory: FIRST_FIT) ---")
schedulers = ["FCFS", "SJF", "SRTF", "RR", "Priority"]
print(f"{'Scheduler':<10} | {'CPU Util %':<10} | {'Avg Wait':<10} | {'Avg Resp':<10} | {'Avg Turn':<10}")
print("-" * 60)
for sched in schedulers:
    m = run_sim(sched, "FIRST_FIT")
    print(f"{sched:<10} | {m.get('cpu_utilization', 0):<10.2f} | {m.get('avg_waiting_time', 0):<10.2f} | {m.get('avg_response_time', 0):<10.2f} | {m.get('avg_turnaround', 0):<10.2f}")

print("\n--- Memory Strategies (Scheduler: RR) ---")
mem_strategies = ["FIRST_FIT", "BEST_FIT", "WORST_FIT"]
print(f"{'Strategy':<15} | {'CPU Util %':<10} | {'Max Frag %':<10} | {'Avg Turn':<10}")
print("-" * 55)
for strat in mem_strategies:
    m = run_sim("RR", strat)
    print(f"{strat:<15} | {m.get('cpu_utilization', 0):<10.2f} | {m.get('max_fragmentation', 0):<10.2f} | {m.get('avg_turnaround', 0):<10.2f}")
