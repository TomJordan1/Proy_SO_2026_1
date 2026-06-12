#include "json_reader.hpp"
#include "json_writer.hpp"
#include "simulator.hpp"
#include <iostream>
#include <string>

int main(int argc, char* argv[]) {
    // ── Parse arguments ──────────────────────────────────────────────────────
    std::string inputFile  = "escenario_modelo.json";
    std::string outputFile = "output.json";
    int maxTicks = 200;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if ((arg == "-i" || arg == "--input") && i + 1 < argc)
            inputFile = argv[++i];
        else if ((arg == "-o" || arg == "--output") && i + 1 < argc)
            outputFile = argv[++i];
        else if ((arg == "-t" || arg == "--ticks") && i + 1 < argc)
            maxTicks = std::stoi(argv[++i]);
        else if (arg == "-h" || arg == "--help") {
            std::cout << "Usage: simulator [options]\n"
                      << "  -i <file>   Input JSON scenario (default: escenario_modelo.json)\n"
                      << "  -o <file>   Output JSON file (default: output.json)\n"
                      << "  -t <n>      Maximum ticks to simulate (default: 200)\n";
            return 0;
        }
    }

    std::cout << "===========================================\n";
    std::cout << "  OS Simulator - Proyecto Final\n";
    std::cout << "===========================================\n";
    std::cout << "Input  : " << inputFile  << "\n";
    std::cout << "Output : " << outputFile << "\n";
    std::cout << "MaxTicks: " << maxTicks   << "\n\n";

    // ── Load input JSON ──────────────────────────────────────────────────────
    JsonReader reader;
    if (!reader.load(inputFile)) {
        std::cerr << "ERROR: " << reader.errorMessage() << "\n";
        return 1;
    }

    const SimConfig& cfg = reader.config();
    std::cout << "Scenario  : " << cfg.name << "\n";
    std::cout << "Scheduler : " << algoToString(cfg.scheduler) << "\n";
    std::cout << "Memory    : " << cfg.totalMemoryMB << " MB\n";
    std::cout << "Processes : " << reader.processes().size() << "\n";
    std::cout << "Events    : " << cfg.events.size() << "\n\n";

    // ── Create writer ────────────────────────────────────────────────────────
    JsonWriter writer(cfg.name, algoToString(cfg.scheduler),
                      cfg.totalMemoryMB, cfg.numCores);

    // ── Run simulation ───────────────────────────────────────────────────────
    Simulator sim(cfg);
    sim.loadProcesses(reader.processes());

    std::cout << "Running simulation...\n";
    sim.run(maxTicks, writer);

    std::cout << "\n=== Simulation complete ===\n";
    std::cout << "Completed processes : " << sim.completedProcesses() << "\n";
    std::cout << "Context switches    : " << sim.totalContextSwitches() << "\n";
    std::cout << "Avg turnaround      : " << sim.avgTurnaround() << " ticks\n";
    std::cout << "Avg waiting         : " << sim.avgWaiting()    << " ticks\n";
    std::cout << "Avg response        : " << sim.avgResponse()   << " ticks\n";

    // ── Write output JSON ────────────────────────────────────────────────────
    if (!writer.write(outputFile)) {
        std::cerr << "ERROR: Failed to write output file: " << outputFile << "\n";
        return 1;
    }

    std::cout << "\nOutput written to: " << outputFile << "\n";
    return 0;
}
