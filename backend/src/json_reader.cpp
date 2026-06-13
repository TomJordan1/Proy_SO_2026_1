#include "json_reader.hpp"
#include "../include/nlohmann/json.hpp"
#include <fstream>
#include <stdexcept>

using json = nlohmann::json;

// Helper: get value or default
template<typename T>
T jget(const json& j, const std::string& key, T def) {
    if (j.contains(key) && !j[key].is_null()) return j[key].get<T>();
    return def;
}

bool JsonReader::load(const std::string& filepath) {
    try {
        std::ifstream file(filepath);
        if (!file.is_open()) {
            error_ = "Cannot open file: " + filepath;
            return false;
        }

        json root;
        file >> root;

        // ── metadata ──────────────────────────────────────────────────────
        if (root.contains("metadata")) {
            const auto& m = root["metadata"];
            config_.name          = jget<std::string>(m, "name", "Unnamed Simulation");
            config_.executionDate = jget<std::string>(m, "executionDate", "");
            config_.executionTime = jget<std::string>(m, "executionTime", "");
        }

        // ── hardware ──────────────────────────────────────────────────────
        if (root.contains("hardware")) {
            const auto& hw = root["hardware"];

            if (hw.contains("cpu")) {
                const auto& cpu = hw["cpu"];
                config_.numCores       = jget<int>(cpu, "numCores", 1);
                std::string algoStr    = jget<std::string>(cpu, "scheduler", "FCFS");
                config_.scheduler      = parseAlgo(algoStr);
                config_.preemptive     = jget<bool>(cpu, "preemptive", false);
                config_.quantum        = jget<int>(cpu, "quantum", 4);
                config_.contextSwitchCost = jget<int>(cpu, "contextSwitchCostTicks", 1);
            }

            if (hw.contains("memory")) {
                const auto& mem = hw["memory"];
                config_.totalMemoryMB  = jget<int>(mem, "totalMB", 1024);
                config_.osReservedMB   = jget<int>(mem, "osReservedMB", 64);
                config_.minSegmentMB   = jget<int>(mem, "minSegmentMB", 4);
                config_.maxProcessMB   = jget<int>(mem, "maxProcessMB", 256);
                std::string stratStr   = jget<std::string>(mem, "allocationStrategy", "FIRST_FIT");
                config_.strategy       = parseStrategy(stratStr);
                config_.mmuEnabled     = jget<bool>(mem, "mmuEnabled", true);
            }

            if (hw.contains("ioDevices") && hw["ioDevices"].is_array()) {
                for (const auto& dev : hw["ioDevices"]) {
                    IODeviceConfig dc;
                    dc.id      = jget<std::string>(dev, "id", "UNKNOWN");
                    dc.latency = jget<int>(dev, "latency", 10);
                    config_.ioDevices.push_back(dc);
                }
            }
        }

        // ── simulation ────────────────────────────────────────────────────
        if (root.contains("simulation")) {
            const auto& sim = root["simulation"];
            config_.speedMS         = jget<int>(sim, "speedMS", 100);
            config_.errorProbability = jget<double>(sim, "errorProbabilityDecimal", 0.005);
            config_.ioFreqMultiplier = jget<double>(sim, "ioFreqMultiplier", 1.0);
            config_.cpuBoundRatio   = jget<double>(sim, "cpuBoundRatio", 0.5);

            if (sim.contains("aging")) {
                const auto& ag = sim["aging"];
                config_.agingEnabled  = jget<bool>(ag, "enabled", false);
                config_.agingInterval = jget<int>(ag, "interval", 20);
            }
            if (sim.contains("autoCreate")) {
                const auto& ac = sim["autoCreate"];
                config_.autoCreate        = jget<bool>(ac, "enabled", false);
                config_.autoCreateMaxTicks = jget<int>(ac, "maxTicks", 0);
            }
        }

        // ── processes ─────────────────────────────────────────────────────
        if (root.contains("processes") && root["processes"].is_array()) {
            for (const auto& p : root["processes"]) {
                ProcessDef pd;
                pd.name         = jget<std::string>(p, "name", "Process");
                pd.burst_time   = jget<int>(p, "burst_time", 10);
                pd.priority     = jget<int>(p, "priority", 1);
                pd.memory_size  = jget<int>(p, "memory_size", 16);
                pd.process_type = jget<std::string>(p, "process_type", "CPU_BOUND");
                pd.arrival_tick = jget<int>(p, "arrival_tick", 0);
                processes_.push_back(pd);
            }
        }

        // ── events ────────────────────────────────────────────────────────
        if (root.contains("events") && root["events"].is_array()) {
            for (const auto& ev : root["events"]) {
                SimEvent se;
                se.tick   = jget<int>(ev, "tick", 0);
                se.type   = jget<std::string>(ev, "type", "");
                se.pid    = jget<int>(ev, "pid", -1);
                se.action = jget<std::string>(ev, "action", "");
                config_.events.push_back(se);
            }
        }

        return true;

    } catch (const std::exception& ex) {
        error_ = std::string("JSON parse error: ") + ex.what();
        return false;
    }
}
