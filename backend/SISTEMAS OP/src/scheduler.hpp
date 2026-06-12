#pragma once
#include "pcb.hpp"
#include "types.hpp"
#include <vector>
#include <deque>
#include <list>
#include <memory>
#include <functional>

// ─── Process Pool & Queues ────────────────────────────────────────────────────
// All processes are stored in a shared pool; queues hold raw pointers.
using ProcPtr = PCB*;

// ─── Scheduler ──────────────────────────────────────────────────────────────
class Scheduler {
public:
    explicit Scheduler(SchedulerAlgo algo, int quantum = 4, int numMLFQLevels = 3);

    // Select next process from the ready queue (returns nullptr if empty)
    ProcPtr selectNext(std::vector<std::deque<ProcPtr>>& readyQueues);

    // Called when a process is preempted/quantum expires → re-queue it
    void requeue(ProcPtr p, std::vector<std::deque<ProcPtr>>& readyQueues);

    // Admit a new-arriving process into the ready queues
    void admit(ProcPtr p, std::vector<std::deque<ProcPtr>>& readyQueues);

    // Age all waiting processes (boost priority after agingInterval ticks)
    void applyAging(std::vector<std::deque<ProcPtr>>& readyQueues, int currentTick, int agingInterval);

    // Number of MLFQ levels
    int numLevels() const { return numMLFQLevels_; }

    SchedulerAlgo algo() const { return algo_; }
    int quantum() const { return quantum_; }

private:
    SchedulerAlgo algo_;
    int quantum_;
    int numMLFQLevels_;

    ProcPtr selectFCFS   (std::vector<std::deque<ProcPtr>>& rq);
    ProcPtr selectSJF    (std::vector<std::deque<ProcPtr>>& rq);
    ProcPtr selectSRTF   (std::vector<std::deque<ProcPtr>>& rq);
    ProcPtr selectPriority(std::vector<std::deque<ProcPtr>>& rq);
    ProcPtr selectRR     (std::vector<std::deque<ProcPtr>>& rq);
    ProcPtr selectMLFQ   (std::vector<std::deque<ProcPtr>>& rq);
};
