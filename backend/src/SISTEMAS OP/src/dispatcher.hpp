#pragma once
#include "pcb.hpp"
#include "types.hpp"
#include "scheduler.hpp"
#include <string>

// ─── Context Switch Record ────────────────────────────────────────────────────
struct ContextSwitchEvent {
    int      tick;
    int      coreId;
    std::string label;
    std::string fromState;
    std::string toState;
};

// ─── Dispatcher ──────────────────────────────────────────────────────────────
// Handles context switches between processes on a single CPU core.
class Dispatcher {
public:
    explicit Dispatcher(int contextSwitchCostTicks);

    // Save state of outgoing process and load state of incoming process.
    // Returns true if the switch started (overhead may still be pending).
    // While isSwitching() is true, the CPU is "busy with overhead".
    bool contextSwitch(ProcPtr outgoing, ProcPtr incoming, int coreId, int currentTick);

    // Tick the overhead counter. Returns true when overhead is complete.
    bool tick();

    bool isSwitching()          const { return switchRemaining_ > 0; }
    int  switchOverhead()       const { return cost_; }
    int  switchRemaining()      const { return switchRemaining_; }
    int  contextSwitchCount()   const { return switchCount_; }

    const ContextSwitchEvent& lastEvent() const { return lastEvent_; }

private:
    int cost_;
    int switchRemaining_ = 0;
    int switchCount_     = 0;
    ContextSwitchEvent lastEvent_;
};
