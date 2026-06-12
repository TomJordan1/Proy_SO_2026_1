#include "simulator.hpp"
#include <algorithm>
#include <sstream>
#include <cmath>
#include <random>

// ─── static RNG for random IO assignment ─────────────────────────────────────
static std::mt19937 simRng(std::random_device{}());

// ─── Constructor ─────────────────────────────────────────────────────────────
Simulator::Simulator(const SimConfig& cfg)
    : cfg_(cfg),
      scheduler_(cfg.scheduler, cfg.quantum, 3),
      memory_(cfg.totalMemoryMB, cfg.osReservedMB, cfg.minSegmentMB,
              cfg.maxProcessMB, cfg.strategy, cfg.mmuEnabled),
      io_(cfg.ioDevices, cfg.ioFreqMultiplier),
      errors_(cfg.errorProbability)
{
    // Initialize CPU cores
    for (int i = 0; i < cfg.numCores; ++i) {
        cores_.emplace_back(i, cfg.contextSwitchCost);
    }
    // Ready queues: one per MLFQ level (or 1 for other algos)
    int levels = (cfg.scheduler == SchedulerAlgo::MLFQ) ? 3 : 1;
    readyQueues_.resize(levels);
}

// ─── loadProcesses ───────────────────────────────────────────────────────────
void Simulator::loadProcesses(const std::vector<ProcessDef>& defs) {
    for (const auto& def : defs) {
        auto pcb = std::make_unique<PCB>();
        pcb->pid          = ++pidCounter_;
        pcb->name         = def.name;
        pcb->type         = parseProcessType(def.process_type);
        pcb->priority     = def.priority;
        pcb->burstTime    = def.burst_time;
        pcb->remainingTime= def.burst_time;
        pcb->memorySizeMB = def.memory_size;
        pcb->arrivalTick  = def.arrival_tick;
        pcb->state        = ProcessState::NEW;

        // Allocate memory immediately (Long-Term Scheduler pre-allocates)
        if (memory_.allocate(pcb->pid, pcb->name, pcb->memorySizeMB)) {
            pcb->memoryBaseAddress = memory_.baseAddress(pcb->pid);
        }

        pool_.push_back(std::move(pcb));
    }

    // Separate by arrival tick: tick 0 goes to newList ready to admit
    for (auto& up : pool_) {
        newList_.push_back(up.get());
    }

    // Initial log entries
    for (auto* p : newList_) {
        log("[T=0] MANUAL " + std::to_string(p->pid) + " (" + p->name + ") " +
            std::to_string(p->memorySizeMB) + "MB");
    }
}

// ─── run ─────────────────────────────────────────────────────────────────────
void Simulator::run(int maxTicks, JsonWriter& writer) {
    for (int tick = 1; tick <= maxTicks; ++tick) {
        tickLogs_.clear();
        hadCtxEvent_ = false;

        // 1. Admit processes that arrive this tick
        admitNewProcesses(tick);

        // 2. Tick the dispatcher overhead on each core (count down context switches)
        for (auto& core : cores_) {
            if (core.switching) {
                core.dispatcher.tick();
                if (!core.dispatcher.isSwitching()) {
                    core.switching = false;
                }
            }
        }

        // 3. Complete any pending I/O
        processIOCompletions(tick);

        // 4. For free cores, dispatch next process
        dispatchCPUs(tick);

        // 5. Execute one tick of CPU for running processes
        executeOneCPUTick(tick);

        // 6. Error injection
        checkErrors(tick);

        // 7. Process explicit events from JSON input
        processEvents(tick);

        // 8. Aging
        if (cfg_.agingEnabled) {
            applyAging(tick);
        }

        // 9. Increment waiting time for all READY processes
        for (auto& q : readyQueues_) {
            for (auto* p : q) {
                p->waitingTime++;
            }
        }

        // 10. Snapshot and record
        TickSnapshot snap = buildSnapshot(tick);
        writer.recordTick(snap);

        // Early exit if all done
        if (allDone() && newList_.empty()) break;
    }
}

// ─── admitNewProcesses ───────────────────────────────────────────────────────
void Simulator::admitNewProcesses(int tick) {
    auto it = newList_.begin();
    while (it != newList_.end()) {
        PCB* p = *it;
        if (p->arrivalTick <= tick) {
            scheduler_.admit(p, readyQueues_);
            log("[T=" + std::to_string(tick) + "] ADMIT P" +
                std::to_string(p->pid) + " (" + p->name + ")");
            it = newList_.erase(it);
        } else {
            ++it;
        }
    }
}

// ─── processIOCompletions ────────────────────────────────────────────────────
void Simulator::processIOCompletions(int tick) {
    io_.tick([&](int pid, const std::string& deviceId) {
        PCB* p = findProcess(pid);
        if (!p) return;

        p->ioDevice         = std::nullopt;
        p->ioRemainingTicks = 0;
        p->state            = ProcessState::READY;

        // Remove from waiting list
        waitingList_.erase(
            std::remove(waitingList_.begin(), waitingList_.end(), p),
            waitingList_.end());

        // Re-admit to ready queue
        scheduler_.admit(p, readyQueues_);
        log("[T=" + std::to_string(tick) + "] IO_DONE P" +
            std::to_string(pid) + " (" + p->name + ") device=" + deviceId);
    });
}

// ─── dispatchCPUs ────────────────────────────────────────────────────────────
void Simulator::dispatchCPUs(int tick) {
    for (auto& core : cores_) {
        // Skip cores that are mid-switch or already running a process
        if (core.switching) continue;
        if (core.current && core.current->state == ProcessState::RUNNING) continue;

        // Preemptive: check if a better process arrived (SRTF, Priority)
        if (core.current && cfg_.preemptive) {
            bool shouldPreempt = false;
            if (cfg_.scheduler == SchedulerAlgo::SRTF) {
                // Check if any ready process has shorter remaining time
                for (auto& q : readyQueues_) {
                    for (auto* candidate : q) {
                        if (candidate->remainingTime < core.current->remainingTime) {
                            shouldPreempt = true;
                            break;
                        }
                    }
                    if (shouldPreempt) break;
                }
            } else if (cfg_.scheduler == SchedulerAlgo::PRIORITY) {
                for (auto& q : readyQueues_) {
                    for (auto* candidate : q) {
                        if (candidate->priority > core.current->priority) {
                            shouldPreempt = true;
                            break;
                        }
                    }
                    if (shouldPreempt) break;
                }
            } else if (cfg_.scheduler == SchedulerAlgo::RR) {
                if (core.current->quantumUsed >= cfg_.quantum) {
                    shouldPreempt = true;
                }
            }

            if (shouldPreempt) {
                // Put current process back in ready queue
                PCB* outgoing = core.current;
                core.current = nullptr;
                scheduler_.requeue(outgoing, readyQueues_);
                log("[T=" + std::to_string(tick) + "] PREEMPT P" +
                    std::to_string(outgoing->pid) + " (" + outgoing->name + ")");
            }
        }

        if (core.current) continue; // still running, no preemption occurred

        // Select next process
        PCB* next = scheduler_.selectNext(readyQueues_);
        if (!next) continue;

        // Perform context switch
        PCB* outgoing = nullptr; // already cleared above
        core.dispatcher.contextSwitch(outgoing, next, core.id, tick);
        core.current  = next;
        core.switching = (cfg_.contextSwitchCost > 0);

        ++totalCtxSwitches_;
        hadCtxEvent_  = true;
        lastCtxEvent_ = core.dispatcher.lastEvent();
        lastCtxEvent_.toState = "RUNNING";
        lastCtxEvent_.fromState = "READY";

        log("[T=" + std::to_string(tick) + "] CPU" + std::to_string(core.id) +
            ": CTX-IN P" + std::to_string(next->pid) + " (" + next->name + ")" +
            " prio=" + std::to_string(next->priority) +
            " rem=" + std::to_string(next->remainingTime) + "t");
    }
}

// ─── executeOneCPUTick ───────────────────────────────────────────────────────
void Simulator::executeOneCPUTick(int tick) {
    for (auto& core : cores_) {
        PCB* p = core.current;
        if (!p) continue;
        if (core.switching) {
            // Context switch overhead: CPU busy but not decrementing burst
            busyCoreTicks_++;
            continue;
        }
        if (p->state != ProcessState::RUNNING) continue;

        // Advance program counter (simulate instruction fetch)
        p->pc++;
        p->registers.AX = p->pc % 256;
        p->registers.BX = (p->pc / 2) % 256;

        // Decrement remaining burst
        p->remainingTime--;
        p->quantumUsed++;
        busyCoreTicks_++;

        // Random I/O interruption for IO_BOUND and INTERACTIVE processes
        {
            static std::uniform_real_distribution<double> ioDist(0.0, 1.0);
            double ioChance = 0.0;
            if (p->type == ProcessType::IO_BOUND)    ioChance = 0.08;
            if (p->type == ProcessType::INTERACTIVE) ioChance = 0.05;
            ioChance *= cfg_.ioFreqMultiplier;

            if (ioChance > 0.0 && ioDist(simRng) < ioChance && p->remainingTime > 0) {
                // Pick a random device
                const auto& devs = io_.devices();
                if (!devs.empty()) {
                    std::uniform_int_distribution<int> devIdx(0, (int)devs.size()-1);
                    const std::string& devId = devs[devIdx(simRng)].id;
                    p->ioDevice = devId;
                    p->state    = ProcessState::WAITING;
                    io_.requestIO(p->pid, p->name, devId);
                    waitingList_.push_back(p);
                    core.current = nullptr;
                    log("[T=" + std::to_string(tick) + "] IO_REQ P" +
                        std::to_string(p->pid) + " (" + p->name + ") → " + devId);
                    continue;
                }
            }
        }

        // Check if process finished
        if (p->remainingTime <= 0) {
            terminateProcess(p, tick);
            core.current = nullptr;
        }
    }
}

// ─── checkErrors ─────────────────────────────────────────────────────────────
void Simulator::checkErrors(int tick) {
    for (auto& core : cores_) {
        PCB* p = core.current;
        if (!p || p->state != ProcessState::RUNNING) continue;

        if (errors_.tryInjectError(*p, tick)) {
            log("[T=" + std::to_string(tick) + "] ERROR P" +
                std::to_string(p->pid) + " (" + p->name + ") → " +
                errorCodeToString(p->errorCode));
            memory_.free(p->pid);
            ++completedCount_;
            core.current = nullptr;
        }
    }
}

// ─── processEvents ───────────────────────────────────────────────────────────
void Simulator::processEvents(int tick) {
    for (const auto& ev : cfg_.events) {
        if (ev.tick != tick) continue;

        PCB* p = findProcess(ev.pid);
        if (!p) continue;

        if (ev.action == "CANCEL") {
            // Cancel the process's IO
            io_.cancelIO(ev.pid);
            if (p->state == ProcessState::WAITING) {
                p->ioDevice = std::nullopt;
                p->state    = ProcessState::READY;
                waitingList_.erase(
                    std::remove(waitingList_.begin(), waitingList_.end(), p),
                    waitingList_.end());
                scheduler_.admit(p, readyQueues_);
                log("[T=" + std::to_string(tick) + "] EVENT CANCEL P" +
                    std::to_string(ev.pid) + " (" + p->name + ")");
            }
        } else if (ev.action == "WAIT_FOR_SIGNAL") {
            // Block process waiting for manual signal
            if (p->state == ProcessState::RUNNING || p->state == ProcessState::READY) {
                p->state    = ProcessState::WAITING;
                p->ioDevice = ev.type;
                for (auto& core : cores_) {
                    if (core.current == p) core.current = nullptr;
                }
                waitingList_.erase(
                    std::remove(waitingList_.begin(), waitingList_.end(), p),
                    waitingList_.end());
                waitingList_.push_back(p);
                log("[T=" + std::to_string(tick) + "] EVENT WAIT_SIGNAL P" +
                    std::to_string(ev.pid) + " (" + p->name + ")");
            }
        }
    }
}

// ─── applyAging ──────────────────────────────────────────────────────────────
void Simulator::applyAging(int tick) {
    scheduler_.applyAging(readyQueues_, tick, cfg_.agingInterval);
}

// ─── terminateProcess ────────────────────────────────────────────────────────
void Simulator::terminateProcess(PCB* p, int tick) {
    p->state      = ProcessState::TERMINATED;
    p->finishTick = tick;
    p->turnaround = tick - p->arrivalTick;
    p->cpuId      = std::nullopt;

    memory_.free(p->pid);

    sumTurnaround_ += p->turnaround;
    sumWaiting_    += p->waitingTime;
    if (p->responseTime >= 0) sumResponse_ += p->responseTime;
    ++completedCount_;

    log("[T=" + std::to_string(tick) + "] DONE P" +
        std::to_string(p->pid) + " (" + p->name + ") tat=" +
        std::to_string(p->turnaround));
}

// ─── findProcess ─────────────────────────────────────────────────────────────
PCB* Simulator::findProcess(int pid) {
    for (auto& up : pool_) {
        if (up->pid == pid) return up.get();
    }
    return nullptr;
}

// ─── allDone ─────────────────────────────────────────────────────────────────
bool Simulator::allDone() const {
    for (const auto& up : pool_) {
        if (up->state != ProcessState::TERMINATED) return false;
    }
    return true;
}

// ─── Metrics ─────────────────────────────────────────────────────────────────
double Simulator::avgTurnaround() const {
    if (completedCount_ == 0) return 0.0;
    return sumTurnaround_ / completedCount_;
}

double Simulator::avgWaiting() const {
    if (completedCount_ == 0) return 0.0;
    return sumWaiting_ / completedCount_;
}

double Simulator::avgResponse() const {
    if (completedCount_ == 0) return 0.0;
    return sumResponse_ / completedCount_;
}

// ─── buildSnapshot ───────────────────────────────────────────────────────────
TickSnapshot Simulator::buildSnapshot(int tick) const {
    TickSnapshot snap;
    snap.tick        = tick;
    snap.memory      = &memory_;
    snap.ioManager   = &io_;
    snap.scheduler   = algoToString(cfg_.scheduler);

    // Cores
    for (const auto& core : cores_) {
        CoreSnapshot cs;
        cs.id                    = core.id;
        cs.isBusy                = (core.current != nullptr);
        cs.isSwitching           = core.switching;
        cs.switchOverhead        = core.switching ? cfg_.contextSwitchCost : 0;
        cs.switchOverheadRemaining = core.dispatcher.switchRemaining();
        cs.schedulerName         = algoToString(cfg_.scheduler);
        cs.busyTicks             = core.busyTicks;
        cs.process               = core.current;
        snap.cores.push_back(cs);
    }

    // Ready queues (copy)
    snap.readyQueues = readyQueues_;

    // Waiting list (copy)
    snap.waitingList = waitingList_;

    // Process table: all non-terminated + recently terminated
    for (const auto& up : pool_) {
        snap.processTable.push_back(up.get());
    }

    // Metrics
    int totalTicks = tick;
    snap.cpuUtilization = (totalTicks > 0)
        ? (static_cast<double>(busyCoreTicks_) / (totalTicks * cfg_.numCores)) * 100.0
        : 0.0;
    snap.throughput     = (tick > 0) ? static_cast<double>(completedCount_) / tick : 0.0;
    snap.avgTurnaround  = avgTurnaround();
    snap.avgWaiting     = avgWaiting();
    snap.avgResponse    = avgResponse();
    snap.contextSwitches = totalCtxSwitches_;
    snap.starvationEvents = starvationEvents_;
    snap.errorRate      = errors_.errorRate();

    // Timeline
    snap.hasCtxEvent = hadCtxEvent_;
    snap.ctxEvent    = lastCtxEvent_;

    // Console logs
    snap.consoleLogs = tickLogs_;

    return snap;
}

// ─── log ─────────────────────────────────────────────────────────────────────
void Simulator::log(const std::string& msg) {
    tickLogs_.push_back(msg);
}
