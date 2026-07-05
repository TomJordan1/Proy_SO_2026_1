#include "simulator.hpp"
#include <algorithm>
#include <sstream>
#include <cmath>
#include <random>

// ─── static RNG for random IO assignment ─────────────────────────────────────
static std::mt19937 simRng(42);

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

    if (cfg.memoryMode == MemoryMode::PAGED) {
        pagedMemory_ = std::make_unique<PagedMemoryManager>(
            cfg.totalMemoryMB, cfg.osReservedMB, cfg.swapSizeMB,
            cfg.swapDeviceType, cfg.pageTableType, cfg.replacementAlgorithm, cfg.tlbSize
        );
    }
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

        // Generate 5-20 random IOs depending on size and burst (Req Proc-12, Proc-13)
        int numIO = 5 + (pcb->memorySizeMB % 16); 
        if (numIO > 20) numIO = 20;
        if (numIO > pcb->burstTime) numIO = std::max(1, pcb->burstTime / 2);
        
        if (pcb->burstTime > 1) {
            std::uniform_int_distribution<int> ioTickDist(1, pcb->burstTime - 1);
            for(int i = 0; i < numIO; ++i) {
                pcb->plannedIOTicks.push_back(ioTickDist(simRng));
            }
        }

        // Allocate memory immediately (Long-Term Scheduler pre-allocates)
        if (cfg_.memoryMode == MemoryMode::PAGED) {
            if (pagedMemory_->allocateProcess(pcb->pid, pcb->memorySizeMB, 0)) {
                pcb->memoryBaseAddress = 0; // Virtual base address
            } else {
                pcb->state = ProcessState::ERROR;
                pcb->errorCode = ErrorCode::SEGFAULT;
            }
        } else {
            if (memory_.allocate(pcb->pid, pcb->name, pcb->memorySizeMB)) {
                pcb->memoryBaseAddress = memory_.baseAddress(pcb->pid);
            }
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
        
        // Paged memory tick (for algorithms like aging)
        if (cfg_.memoryMode == MemoryMode::PAGED) {
            pagedMemory_->tick(tick);
        }

        // 9. Increment waiting time for all READY processes
        for (auto& q : readyQueues_) {
            for (auto* p : q) {
                p->waitingTime++;
            }
        }

        // 9.5 Medium-Term Scheduler (Suspension/Resumption)
        if (cfg_.memoryMode == MemoryMode::PAGED) {
            ticksSinceLastMtsCheck_++;
            if (ticksSinceLastMtsCheck_ >= 20) {
                int currentPF = totalHardPageFaults_;
                int pfDelta = currentPF - lastPageFaultCount_;
                lastPageFaultCount_ = currentPF;
                ticksSinceLastMtsCheck_ = 0;

                // Thrashing detection: > 4 hard page faults in 20 ticks
                if (pfDelta > 4) {
                    // Suspend a process from ready queue (prefer large/low priority)
                    PCB* victim = nullptr;
                    for (auto it = readyQueues_.rbegin(); it != readyQueues_.rend(); ++it) {
                        for (auto rp = it->begin(); rp != it->end(); ++rp) {
                            if ((*rp)->state == ProcessState::READY) {
                                victim = *rp;
                                it->erase(rp);
                                break;
                            }
                        }
                        if (victim) break;
                    }
                    if (victim) {
                        victim->state = ProcessState::SUSPENDED;
                        suspendedList_.push_back(victim);
                        log("[T=" + std::to_string(tick) + "] MTS: Suspending P" + std::to_string(victim->pid) + " due to Thrashing");
                        pagedMemory_->freeProcess(victim->pid); // Free its RAM pages (swap them out)
                    }
                } else if (pfDelta == 0 && !suspendedList_.empty()) {
                    // Memory pressure is low, resume a process
                    PCB* p = suspendedList_.front();
                    suspendedList_.erase(suspendedList_.begin());
                    if (pagedMemory_->allocateProcess(p->pid, p->memorySizeMB, tick)) {
                        p->state = ProcessState::READY;
                        scheduler_.admit(p, readyQueues_);
                        log("[T=" + std::to_string(tick) + "] MTS: Resuming P" + std::to_string(p->pid));
                    } else {
                        suspendedList_.push_back(p);
                    }
                }
            }
        }

        // 10. Snapshot and record
        TickSnapshot snap = buildSnapshot(tick);
        writer.recordTick(snap);

        // 11. Check for unresolved KEYBOARD IO to halt simulation
        bool unresolvedKeyboard = false;
        for (const auto& dev : io_.devices()) {
            if (dev.id == "KEYBOARD" && dev.busy && dev.current && !dev.current->resolved) {
                unresolvedKeyboard = true;
                break;
            }
        }
        if (unresolvedKeyboard) {
            log("[T=" + std::to_string(tick) + "] HALTING for KEYBOARD interrupt (awaiting user action).");
            break;
        }

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
            
            // Pre-page: eagerly load initial working set pages into RAM on arrival.
            // This creates real memory pressure across multiple processes.
            if (cfg_.memoryMode == MemoryMode::PAGED && pagedMemory_) {
                int maxPages = (p->memorySizeMB * 1024) / PAGE_SIZE_KB;
                int prePagesCount = std::max(1, (int)(maxPages * 0.15)); // Pre-load 15% of pages
                for (int i = 0; i < prePagesCount && i < maxPages; ++i) {
                    pagedMemory_->accessPage(p->pid, i, SegmentType::DATA, tick, false);
                }
            }
            
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

    // Handle Page Fault Completions
    auto it = waitingList_.begin();
    while (it != waitingList_.end()) {
        PCB* p = *it;
        if (p->ioDevice.has_value() && p->ioDevice.value() == "PAGE_FAULT") {
            p->pageFaultRemainingTicks--;
            if (p->pageFaultRemainingTicks <= 0) {
                p->ioDevice = std::nullopt;
                p->state = ProcessState::READY;
                it = waitingList_.erase(it);
                scheduler_.admit(p, readyQueues_);
                log("[T=" + std::to_string(tick) + "] PAGE_LOADED P" + std::to_string(p->pid) + " (" + p->name + ")");
                continue;
            }
        }
        ++it;
    }
}

// ─── dispatchCPUs ────────────────────────────────────────────────────────────
void Simulator::dispatchCPUs(int tick) {
    for (auto& core : cores_) {
        // Skip cores that are mid-switch
        if (core.switching) continue;

        // Preemptive: check if a better process arrived (SRTF, Priority) or Quantum expired
        if (core.current && core.current->state == ProcessState::RUNNING && cfg_.preemptive) {
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
            // Note: RR quantum preemption is handled directly in executeOneCPUTick
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

        log("[T=" + std::to_string(tick) + "] [CTX SWITCH] CPU" + std::to_string(core.id) +
            " -> Entra P" + std::to_string(next->pid) + " (" + next->name + ")" +
            (core.switching ? " (Overhead: " + std::to_string(cfg_.contextSwitchCost) + "t)" : ""));
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

        if (cfg_.memoryMode == MemoryMode::PAGED) {
            bool pageFaultOccurred = false;
            int accessesPerTick = 50; // Batch of memory accesses to simulate real CPU speed
            int maxPages = (p->memorySizeMB * 1024) / PAGE_SIZE_KB;

            // Initialize memory pattern lazily for the process
            if (p->memWorkingSetSize <= 1 && maxPages > 0) {
                std::uniform_int_distribution<int> typeDist(0, 1);
                p->accessPattern = (typeDist(simRng) == 0) ? MemoryAccessPattern::SEQUENTIAL : MemoryAccessPattern::LOCALITY;
                // Working set at 30% of process pages to create real memory pressure and trigger swap
                p->memWorkingSetSize = std::max(1, (int)(maxPages * 0.30)); 
                p->memWorkingSetBase = 0;
                p->memCurrentVpn = 0;
            }

            for (int i = 0; i < accessesPerTick; ++i) {
                int vpn = p->memCurrentVpn;
                
                // 95% spatial locality (stay in the same 4KB page for multiple accesses)
                std::uniform_real_distribution<double> spatialDist(0.0, 1.0);
                if (spatialDist(simRng) > 0.95 && maxPages > 0) {
                    if (p->accessPattern == MemoryAccessPattern::SEQUENTIAL) {
                        p->memCurrentVpn = (p->memCurrentVpn + 1) % maxPages;
                        vpn = p->memCurrentVpn;
                    } else {
                        // LOCALITY (80-20 rule)
                        std::uniform_real_distribution<double> dist(0.0, 1.0);
                        if (dist(simRng) < 0.8) {
                            std::uniform_int_distribution<int> wsDist(0, p->memWorkingSetSize - 1);
                            vpn = (p->memWorkingSetBase + wsDist(simRng)) % maxPages;
                        } else {
                            std::uniform_int_distribution<int> anyDist(0, maxPages - 1);
                            vpn = anyDist(simRng);
                        }
                        
                        // Slowly drift the working set
                        if (dist(simRng) < 0.05) {
                            p->memWorkingSetBase = (p->memWorkingSetBase + 1) % maxPages;
                        }
                        p->memCurrentVpn = vpn;
                    }
                }

                int penalty = pagedMemory_->accessPage(p->pid, vpn, SegmentType::DATA, tick, false);
                if (penalty == -1) {
                    // Segfault / OOM
                    failProcess(p, tick, ErrorCode::SEGFAULT);
                    core.current = nullptr;
                    log("[T=" + std::to_string(tick) + "] ERROR P" + std::to_string(p->pid) + " (PAGE_FAULT OOM)");
                    pageFaultOccurred = true;
                    break;
                } else if (penalty > 0) {
                    if (penalty == 1) {
                        // TLB Miss, PT Hit (Hardware page walk) -> Stall CPU but do not context switch
                        // We don't abort the batch. The hardware resolves it and continues execution.
                        continue;
                    } else {
                        // Hard Page Fault (Disk I/O required) -> Context switch to WAITING
                        p->state = ProcessState::WAITING;
                        p->ioDevice = "PAGE_FAULT";
                        p->pageFaultRemainingTicks = penalty;
                        p->interruptCount++;
                        p->interruptHistory.push_back("Page Fault (Swap I/O)");
                        totalHardPageFaults_++;
                        waitingList_.push_back(p);
                        core.current = nullptr;
                        log("[T=" + std::to_string(tick) + "] PAGE_FAULT P" + std::to_string(p->pid) + " penalty=" + std::to_string(penalty));
                        pageFaultOccurred = true;
                        break;
                    }
                }
            }

            if (pageFaultOccurred) {
                continue; // Skip decrementing burst time and quantum since the CPU stalled
            }
        }

        // Decrement remaining burst
        p->remainingTime--;
        p->quantumUsed++;
        busyCoreTicks_++;

        // ── Quantum expiry (RR): preempt immediately after this tick ─────────
        if ((cfg_.scheduler == SchedulerAlgo::RR || cfg_.scheduler == SchedulerAlgo::MLFQ)
            && p->quantumUsed >= cfg_.quantum
            && p->remainingTime > 0)
        {
            log("[T=" + std::to_string(tick) + "] QUANTUM_EXP P" +
                std::to_string(p->pid) + " (" + p->name + ")" +
                " [" + std::to_string(p->quantumUsed) + "/" + std::to_string(cfg_.quantum) + " ticks]");
            scheduler_.requeue(p, readyQueues_);
            core.current = nullptr;
            continue;
        }

        // I/O interruption based on planned ticks (Req Proc-12, Proc-13)
        if (p->state != ProcessState::WAITING && p->remainingTime > 0) {
            auto it = std::find(p->plannedIOTicks.begin(), p->plannedIOTicks.end(), p->pc);
            if (it != p->plannedIOTicks.end()) {
                p->plannedIOTicks.erase(it); // Consume the interrupt

                std::uniform_int_distribution<int> paramsDist(1, 100);
                std::string params = "REQ_" + std::to_string(paramsDist(simRng));
                
                // random duration between 5 and 20 ticks
                std::string devId = io_.randomInterrupt(p->pid, p->name, 5, 20, params);
                if (!devId.empty()) {
                    p->ioDevice = devId;
                    p->state    = ProcessState::WAITING;
                    p->interruptCount++;
                    p->interruptHistory.push_back("I/O Device: " + devId + ", Params: " + params);
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

    // ── Memory pressure: READY processes touch their resident pages ──────────
    // This simulates that loaded processes keep their working set in RAM,
    // creating real memory pressure and triggering swap eviction when RAM fills.
    if (cfg_.memoryMode == MemoryMode::PAGED && (tick % 10 == 0)) {
        for (auto& q : readyQueues_) {
            for (PCB* rp : q) {
                if (!rp || rp->state != ProcessState::READY) continue;
                int maxPages = (rp->memorySizeMB * 1024) / PAGE_SIZE_KB;
                if (maxPages <= 0) continue;
                // Touch a small number of pages to keep them referenced
                int touchCount = std::min(3, rp->memWorkingSetSize);
                for (int i = 0; i < touchCount; ++i) {
                    int vpn = (rp->memWorkingSetBase + i) % maxPages;
                    pagedMemory_->accessPage(rp->pid, vpn, SegmentType::DATA, tick, false);
                }
            }
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
            failProcess(p, tick, p->errorCode);
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
                p->state    = ProcessState::ERROR;
                p->errorCode = ErrorCode::CANCEL_USR;
                p->finishTick = tick;
                waitingList_.erase(
                    std::remove(waitingList_.begin(), waitingList_.end(), p),
                    waitingList_.end());
                if (cfg_.memoryMode == MemoryMode::PAGED) {
                    pagedMemory_->freeProcess(ev.pid);
                } else {
                    memory_.free(ev.pid);
                }
                completedCount_++;
                log("[T=" + std::to_string(tick) + "] EVENT CANCEL P" +
                    std::to_string(ev.pid) + " (" + p->name + ") - Aborted");
            }
        } else if (ev.action == "CONTINUE") {
            // Resolve the process's IO so it can begin ticking down its configured latency
            io_.resolveIO(ev.pid);
            log("[T=" + std::to_string(tick) + "] EVENT CONTINUE P" +
                std::to_string(ev.pid) + " (" + p->name + ")");

        } else if (ev.action == "WAIT_FOR_SIGNAL") {
            // Block process waiting for manual signal
            if (p->state == ProcessState::RUNNING || p->state == ProcessState::READY) {
                p->state    = ProcessState::WAITING;
                p->ioDevice = ev.type;
                for (auto& core : cores_) {
                    if (core.current == p) core.current = nullptr;
                }
                // erase+push_back guarantees a single entry even if called twice
                waitingList_.erase(
                    std::remove(waitingList_.begin(), waitingList_.end(), p),
                    waitingList_.end());
                waitingList_.push_back(p);
                log("[T=" + std::to_string(tick) + "] EVENT WAIT_SIGNAL P" +
                    std::to_string(ev.pid) + " (" + p->name + ")");
            }
            // If already WAITING (e.g. random IO fired this same tick), skip silently
        } else if (ev.action == "WAIT_CHILD") {
            if (p->state == ProcessState::RUNNING || p->state == ProcessState::READY) {
                p->state    = ProcessState::WAITING;
                p->ioDevice = "CHILD_PROCESS";
                for (auto& core : cores_) {
                    if (core.current == p) core.current = nullptr;
                }
                waitingList_.erase(
                    std::remove(waitingList_.begin(), waitingList_.end(), p),
                    waitingList_.end());
                waitingList_.push_back(p);
                log("[T=" + std::to_string(tick) + "] EVENT WAIT_CHILD P" +
                    std::to_string(ev.pid) + " (" + p->name + ")");
            }
        }
    }
}

// ─── applyAging ──────────────────────────────────────────────────────────────
void Simulator::applyAging(int tick) {
    scheduler_.applyAging(readyQueues_, tick, cfg_.agingInterval);
}

void Simulator::failProcess(PCB* p, int tick, ErrorCode err) {
    p->errorCode = err;
    terminateProcess(p, tick);
    p->state = ProcessState::ERROR;
}

// ─── terminateProcess ────────────────────────────────────────────────────────
void Simulator::terminateProcess(PCB* p, int tick) {
    p->state      = ProcessState::TERMINATED;
    p->finishTick = tick;
    p->turnaround = tick - p->arrivalTick;
    p->cpuId      = std::nullopt;

    if (cfg_.memoryMode == MemoryMode::PAGED) {
        pagedMemory_->freeProcess(p->pid);
    } else {
        memory_.free(p->pid);
    }

    if (p->parentPid.has_value()) {
        PCB* parent = findProcess(p->parentPid.value());
        if (parent && parent->state == ProcessState::WAITING && parent->ioDevice == "CHILD_PROCESS") {
            parent->ioDevice = std::nullopt;
            parent->state = ProcessState::READY;
            waitingList_.erase(
                std::remove(waitingList_.begin(), waitingList_.end(), parent),
                waitingList_.end());
            scheduler_.admit(parent, readyQueues_);
            log("[T=" + std::to_string(tick) + "] CHILD_DONE P" + std::to_string(p->pid) + " wakes up Parent P" + std::to_string(parent->pid));
        }
    }

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
        if (up->state != ProcessState::TERMINATED && up->state != ProcessState::ERROR) return false;
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
    snap.pagedMemory = pagedMemory_.get();
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
    snap.totalErrors      = errors_.errorCount();
    snap.totalCompleted   = completedCount_;

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
