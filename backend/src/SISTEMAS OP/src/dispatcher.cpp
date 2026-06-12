#include "dispatcher.hpp"

Dispatcher::Dispatcher(int contextSwitchCostTicks)
    : cost_(contextSwitchCostTicks), switchRemaining_(0), switchCount_(0) {}

bool Dispatcher::contextSwitch(ProcPtr outgoing, ProcPtr incoming, int coreId, int currentTick) {
    // ── Save outgoing context ─────────────────────────────────────────────
    if (outgoing) {
        // Registers and PC are already in the PCB struct
        // (they get updated every tick by the CPU execution step)
        // Move outgoing back to READY if it still has work, else leave as WAITING/TERMINATED
        if (outgoing->state == ProcessState::RUNNING) {
            outgoing->state = ProcessState::READY;
            outgoing->cpuId = std::nullopt;
        }
    }

    // ── Load incoming context ─────────────────────────────────────────────
    if (incoming) {
        incoming->cpuId = coreId;
        incoming->state = ProcessState::RUNNING;

        // Record first response time
        if (incoming->responseTime < 0) {
            incoming->responseTime = currentTick - incoming->arrivalTick;
            incoming->startTick    = currentTick;
        }
    }

    // ── Start overhead counter ────────────────────────────────────────────
    switchRemaining_ = cost_;
    ++switchCount_;

    // Record the event
    lastEvent_ = {
        currentTick,
        coreId,
        incoming ? (std::to_string(incoming->pid) + "(" + incoming->name + ")") : "idle",
        outgoing ? stateToString(outgoing->state) : "NONE",
        incoming ? "RUNNING" : "IDLE"
    };

    return true;
}

bool Dispatcher::tick() {
    if (switchRemaining_ > 0) {
        --switchRemaining_;
    }
    return switchRemaining_ == 0;
}
