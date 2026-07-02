import json
import subprocess
import os
import copy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(BASE_DIR, "shared_data", "input.json")
SIMULATOR_EXE = os.path.join(BASE_DIR, "backend", "simulator.exe")
REPORT_FILE = os.path.join(BASE_DIR, "shared_data", "benchmark_report.md")

STRATEGIES = ["FIRST_FIT", "BEST_FIT", "WORST_FIT"]

def run_benchmark():
    if not os.path.exists(INPUT_FILE):
        print(f"File {INPUT_FILE} not found.")
        return
        
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        base_scenario = json.load(f)
        
    # We must use CONTIGUOUS mode to test these allocation strategies
    base_scenario["hardware"]["memory"]["mode"] = "CONTIGUOUS"
    # Ensure memory is large enough to observe fragmentation
    base_scenario["hardware"]["memory"]["totalMB"] = 512
    base_scenario["hardware"]["memory"]["osReservedMB"] = 32
    
    # Increase the number of processes to ensure memory pressure
    if len(base_scenario["processes"]) < 20:
        base_procs = copy.deepcopy(base_scenario["processes"])
        import random
        for i in range(15):
            p = copy.deepcopy(base_procs[i % len(base_procs)])
            p["name"] = f"App_{len(base_scenario['processes']) + 1}"
            p["arrival_tick"] = random.randint(0, 20)
            p["memory_size"] = random.randint(10, 60)
            p["burst_time"] = random.randint(5, 15)
            base_scenario["processes"].append(p)
    
    results = {}
    
    for strategy in STRATEGIES:
        scenario = copy.deepcopy(base_scenario)
        scenario["hardware"]["memory"]["allocationStrategy"] = strategy
        
        temp_input = os.path.join(BASE_DIR, f"temp_input_{strategy}.json")
        temp_output = os.path.join(BASE_DIR, f"temp_output_{strategy}.json")
        
        with open(temp_input, "w", encoding="utf-8") as f:
            json.dump(scenario, f, indent=2)
            
        print(f"Running simulation for {strategy}...")
        try:
            result = subprocess.run(
                [SIMULATOR_EXE, "-i", temp_input, "-o", temp_output, "-t", "50000"],
                cwd=os.path.join(BASE_DIR, "backend"),
                capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"Error running {strategy}: {e.stderr}")
            continue
            
        if os.path.exists(temp_output):
            with open(temp_output, "r", encoding="utf-8") as f:
                output_data = json.load(f)
                
            # Get metrics from the last snapshot/tick
            if output_data and "ticks" in output_data:
                ticks_data = output_data["ticks"]
                # Fallback to look at the last snapshot
                last_snap = None
                for frame in reversed(ticks_data):
                    if frame.get("type") == "snapshot":
                        last_snap = frame.get("state", frame)
                        break
                    elif "type" not in frame: # legacy fallback
                        last_snap = frame
                        break
                        
                if last_snap and "metrics" in last_snap:
                    results[strategy] = last_snap["metrics"]
                else:
                    print(f"No metrics found for {strategy}")
            else:
                print(f"Empty output for {strategy}")
                
        # Clean up temp files
        try:
            os.remove(temp_input)
            os.remove(temp_output)
        except:
            pass
            
    # Generate Markdown Report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("# Memory Allocation Strategies Benchmark Report\n\n")
        f.write("Este reporte compara el rendimiento ('performance') y fraccionamiento de memoria utilizando las tres estrategias de asignación contigua: **FIRST_FIT**, **BEST_FIT**, y **WORST_FIT**.\n\n")
        
        f.write("## Resultados\n\n")
        f.write("| Estrategia | Fragmentación Externa | Context Switches | Avg Turnaround | Avg Waiting | Avg Response |\n")
        f.write("|------------|-----------------------|------------------|----------------|-------------|--------------|\n")
        
        best_frag_val = float('inf')
        best_frag_strat = ""
        best_perf_val = float('inf')
        best_perf_strat = ""
        
        for strategy in STRATEGIES:
            m = results.get(strategy)
            if not m:
                f.write(f"| {strategy} | N/A | N/A | N/A | N/A | N/A |\n")
                continue
                
            # Extraer métricas
            ext_frag = m.get("external_fragmentation_mb", 0)
            ctx_sw = m.get("context_switches", 0)
            avg_turn = m.get("avg_turnaround_time", 0)
            avg_wait = m.get("avg_waiting_time", 0)
            avg_resp = m.get("avg_response_time", 0)
            
            f.write(f"| {strategy} | {ext_frag} MB | {ctx_sw} | {avg_turn:.2f} | {avg_wait:.2f} | {avg_resp:.2f} |\n")
            
            # Análisis
            if ext_frag < best_frag_val:
                best_frag_val = ext_frag
                best_frag_strat = strategy
                
            if avg_turn < best_perf_val:
                best_perf_val = avg_turn
                best_perf_strat = strategy
                
        f.write("\n## Conclusiones\n\n")
        if best_frag_strat:
            f.write(f"- **Optimización de Fraccionamiento:** La estrategia **{best_frag_strat}** resultó ser la más eficiente, presentando una menor fragmentación externa.\n")
        if best_perf_strat:
            f.write(f"- **Rendimiento (Performance):** La estrategia **{best_perf_strat}** demostró ser la más eficiente en términos de rendimiento (menor Turnaround promedio), al asignar más rápido la memoria.\n")
        
    print(f"Reporte generado en: {REPORT_FILE}")

if __name__ == "__main__":
    run_benchmark()
