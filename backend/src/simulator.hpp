#pragma once
#include "types.hpp"
#include "pcb.hpp"
#include "scheduler.hpp"
#include "dispatcher.hpp"
#include "memory_manager.hpp"
#include "io_manager.hpp"
#include "error_manager.hpp"
#include "json_writer.hpp"
#include <vector>
#include <deque>
#include <memory>
#include <string>

// ─── CPU Core State ──────────────────────────────────────────────────────────
struct CPUCore {
    int      id;
    PCB*     current    = nullptr;   // currently running process
    bool     switching  = false;     // in context switch overhead
    int      busyTicks  = 0;
    Dispatcher dispatcher;

    explicit CPUCore(int id, int ctxCost)
        : id(id), dispatcher(ctxCost) {}
};

// ─── Simulator ───────────────────────────────────────────────────────────────
class Simulator {
public:
    explicit Simulator(const SimConfig& cfg);

    // Load processes from their definitions.
    // PIDs are assigned sequentially starting from 1.
    void loadProcesses(const std::vector<ProcessDef>& defs);

    // Run the full simulation for maxTicks ticks.
    void run(int maxTicks, JsonWriter& writer);

    // Performance metrics (final)
    int    totalContextSwitches()  const { return totalCtxSwitches_; }
    int    completedProcesses()    const { return completedCount_; }
    double avgTurnaround()         const;
    double avgWaiting()            const;
    double avgResponse()           const;

private:
    SimConfig cfg_;

    // Process pool (heap-allocated, stable addresses)
    std::vector<std::unique_ptr<PCB>> pool_;

    // Queues
    std::vector<std::deque<PCB*>> readyQueues_;   // [level] → deque of PCBs
    std::vector<PCB*>             waitingList_;   // blocked on I/O
    std::vector<PCB*>             newList_;       // not yet admitted

    // CPU cores
    std::vector<CPUCore> cores_;

    // Sub-systems
    Scheduler        scheduler_;
    MemoryManager    memory_;
    IOManager        io_;
    ErrorManager     errors_;

    // Metrics accumulators
    int    totalCtxSwitches_    = 0;
    int    completedCount_      = 0;
    int    starvationEvents_    = 0;
    int    busyCoreTicks_       = 0;
    double sumTurnaround_       = 0;
    double sumWaiting_          = 0;
    double sumResponse_         = 0;

    // Last context switch event (for writer)
    ContextSwitchEvent lastCtxEvent_;
    bool               hadCtxEvent_ = false;

    // Console log buffer for current tick
    std::vector<std::string> tickLogs_;

    // ── Simulation steps ─────────────────────────────────────────────────────
    void admitNewProcesses(int tick);
    void processIOCompletions(int tick);
    void dispatchCPUs(int tick);
    void executeOneCPUTick(int tick);
    void checkErrors(int tick);
    void processEvents(int tick);
    void applyAging(int tick);

    // ── Helpers ──────────────────────────────────────────────────────────────
    PCB*   findProcess(int pid);
    void   terminateProcess(PCB* p, int tick);
    bool   allDone() const;
    int    pidCounter_ = 0;

    TickSnapshot buildSnapshot(int tick) const;
    void log(const std::string& msg);
};
