#pragma once
#include "types.hpp"
#include "pcb.hpp"
#include "memory_manager.hpp"
#include "io_manager.hpp"
#include "dispatcher.hpp"
#include "../include/nlohmann/json.hpp"
#include <string>
#include <vector>
#include <deque>
#include <optional>

using json = nlohmann::json;

// ─── Per-core CPU state snapshot ─────────────────────────────────────────────
struct CoreSnapshot {
    int         id;
    bool        isBusy;
    bool        isSwitching;
    int         switchOverhead;
    int         switchOverheadRemaining;
    std::string schedulerName;
    int         busyTicks;
    PCB*        process;    // nullptr if idle
};

// ─── Full tick snapshot ───────────────────────────────────────────────────────
struct TickSnapshot {
    int tick;
    std::vector<CoreSnapshot>           cores;
    std::vector<std::deque<PCB*>>       readyQueues;
    std::vector<PCB*>                   waitingList;
    std::vector<PCB*>                   processTable;
    const MemoryManager*                memory;
    const IOManager*                    ioManager;
    // Metrics
    double   cpuUtilization;
    double   throughput;
    double   avgTurnaround;
    double   avgWaiting;
    double   avgResponse;
    int      contextSwitches;
    int      starvationEvents;
    double   errorRate;
    // Events for this tick
    ContextSwitchEvent ctxEvent;
    bool               hasCtxEvent;
    // Console log lines generated this tick
    std::vector<std::string> consoleLogs;
    std::string scheduler;
};

// ─── JSON Writer ─────────────────────────────────────────────────────────────
class JsonWriter {
public:
    JsonWriter(const std::string& simulationName,
               const std::string& schedulerName,
               int totalMemoryMB,
               int numCpus);

    // Record a tick snapshot
    void recordTick(const TickSnapshot& snap);

    // Write the complete output JSON to a file
    bool write(const std::string& filepath) const;

private:
    std::string simName_;
    std::string schedulerName_;
    int totalMemoryMB_;
    int numCpus_;
    json output_;   // accumulates all ticks

    json serializeCore(const CoreSnapshot& core) const;
    json serializeReadyQueue(const std::deque<PCB*>& q) const;
    json serializeWaiting(const std::vector<PCB*>& waiting) const;
    json serializeProcessTable(const std::vector<PCB*>& table) const;
    json serializeMemory(const MemoryManager& mem) const;
    json serializeIODevices(const IOManager& io) const;
    json serializeMetrics(const TickSnapshot& snap) const;
    json serializeTimeline(const TickSnapshot& snap) const;
};
