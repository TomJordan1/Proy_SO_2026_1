#include "scheduler.hpp"
#include <algorithm>
#include <climits>

// ─── Constructor ─────────────────────────────────────────────────────────────
Scheduler::Scheduler(SchedulerAlgo algo, int quantum, int numMLFQLevels)
    : algo_(algo), quantum_(quantum), numMLFQLevels_(numMLFQLevels) {}

// ─── Public: selectNext ───────────────────────────────────────────────────────
ProcPtr Scheduler::selectNext(std::vector<std::deque<ProcPtr>>& rq) {
    switch (algo_) {
        case SchedulerAlgo::FCFS:     return selectFCFS(rq);
        case SchedulerAlgo::SJF:      return selectSJF(rq);
        case SchedulerAlgo::SRTF:     return selectSRTF(rq);
        case SchedulerAlgo::PRIORITY: return selectPriority(rq);
        case SchedulerAlgo::RR:       return selectRR(rq);
        case SchedulerAlgo::MLFQ:     return selectMLFQ(rq);
    }
    return nullptr;
}

// ─── Public: admit ────────────────────────────────────────────────────────────
void Scheduler::admit(ProcPtr p, std::vector<std::deque<ProcPtr>>& rq) {
    if (rq.empty()) rq.resize(numMLFQLevels_);
    // MLFQ: new processes start at level 0 (highest priority queue)
    // All others go to the single queue [0]
    int level = (algo_ == SchedulerAlgo::MLFQ) ? p->mlfqLevel : 0;
    if (level >= (int)rq.size()) level = (int)rq.size() - 1;
    p->state = ProcessState::READY;
    rq[level].push_back(p);
}

// ─── Public: requeue ──────────────────────────────────────────────────────────
void Scheduler::requeue(ProcPtr p, std::vector<std::deque<ProcPtr>>& rq) {
    if (rq.empty()) rq.resize(numMLFQLevels_);
    if (algo_ == SchedulerAlgo::MLFQ) {
        // Demote to next level on quantum expiry
        if (p->mlfqLevel < numMLFQLevels_ - 1)
            p->mlfqLevel++;
    }
    int level = (algo_ == SchedulerAlgo::MLFQ) ? p->mlfqLevel : 0;
    if (level >= (int)rq.size()) level = (int)rq.size() - 1;
    p->state = ProcessState::READY;
    p->quantumUsed = 0;
    rq[level].push_back(p);
}

// ─── Public: applyAging ───────────────────────────────────────────────────────
void Scheduler::applyAging(std::vector<std::deque<ProcPtr>>& rq, int currentTick, int agingInterval) {
    if (agingInterval <= 0) return;
    if (currentTick % agingInterval != 0) return;

    for (auto& queue : rq) {
        for (auto& p : queue) {
            // Boost priority (lower number = higher priority for most algos)
            if (p->priority > 1) {
                p->priority--;
            }
            // For MLFQ, promote to a higher-priority queue
            if (algo_ == SchedulerAlgo::MLFQ && p->mlfqLevel > 0) {
                p->mlfqLevel--;
            }
        }
    }
    // Re-sort each queue for priority-based algos
    if (algo_ == SchedulerAlgo::MLFQ) {
        // Rebuild queues: move processes to their (possibly new) level
        std::vector<ProcPtr> displaced;
        for (int lvl = 1; lvl < (int)rq.size(); ++lvl) {
            auto& q = rq[lvl];
            auto it = q.begin();
            while (it != q.end()) {
                if ((*it)->mlfqLevel < lvl) {
                    displaced.push_back(*it);
                    it = q.erase(it);
                } else {
                    ++it;
                }
            }
        }
        for (auto* p : displaced) {
            int lv = std::max(0, p->mlfqLevel);
            rq[lv].push_back(p);
        }
    }
}

// ─── FCFS ────────────────────────────────────────────────────────────────────
// Pick the process that has been waiting the longest (front of queue 0)
ProcPtr Scheduler::selectFCFS(std::vector<std::deque<ProcPtr>>& rq) {
    for (auto& q : rq) {
        if (!q.empty()) {
            ProcPtr p = q.front();
            q.pop_front();
            return p;
        }
    }
    return nullptr;
}

// ─── SJF (non-preemptive) ────────────────────────────────────────────────────
// Pick the process with the shortest burst time
ProcPtr Scheduler::selectSJF(std::vector<std::deque<ProcPtr>>& rq) {
    ProcPtr best = nullptr;
    std::deque<ProcPtr>* bestQueue = nullptr;
    int bestIdx = -1;

    for (auto& q : rq) {
        for (int i = 0; i < (int)q.size(); ++i) {
            ProcPtr p = q[i];
            if (best == nullptr || p->burstTime < best->burstTime) {
                best = p;
                bestQueue = &q;
                bestIdx = i;
            }
        }
    }
    if (best) {
        bestQueue->erase(bestQueue->begin() + bestIdx);
    }
    return best;
}

// ─── SRTF (preemptive SJF) ───────────────────────────────────────────────────
// Pick the process with the shortest remaining time
ProcPtr Scheduler::selectSRTF(std::vector<std::deque<ProcPtr>>& rq) {
    ProcPtr best = nullptr;
    std::deque<ProcPtr>* bestQueue = nullptr;
    int bestIdx = -1;

    for (auto& q : rq) {
        for (int i = 0; i < (int)q.size(); ++i) {
            ProcPtr p = q[i];
            if (best == nullptr || p->remainingTime < best->remainingTime) {
                best = p;
                bestQueue = &q;
                bestIdx = i;
            }
        }
    }
    if (best) {
        bestQueue->erase(bestQueue->begin() + bestIdx);
    }
    return best;
}

// ─── Priority ────────────────────────────────────────────────────────────────
// Higher numeric priority = higher importance (higher number wins)
ProcPtr Scheduler::selectPriority(std::vector<std::deque<ProcPtr>>& rq) {
    ProcPtr best = nullptr;
    std::deque<ProcPtr>* bestQueue = nullptr;
    int bestIdx = -1;

    for (auto& q : rq) {
        for (int i = 0; i < (int)q.size(); ++i) {
            ProcPtr p = q[i];
            if (best == nullptr || p->priority > best->priority) {
                best = p;
                bestQueue = &q;
                bestIdx = i;
            }
        }
    }
    if (best) {
        bestQueue->erase(bestQueue->begin() + bestIdx);
    }
    return best;
}

// ─── Round Robin ─────────────────────────────────────────────────────────────
// Simply take the front process from the queue
ProcPtr Scheduler::selectRR(std::vector<std::deque<ProcPtr>>& rq) {
    return selectFCFS(rq); // RR rotation is managed by the Dispatcher
}

// ─── MLFQ ────────────────────────────────────────────────────────────────────
// Pick from the highest-priority (lowest index) non-empty queue
ProcPtr Scheduler::selectMLFQ(std::vector<std::deque<ProcPtr>>& rq) {
    return selectFCFS(rq); // queues are already layered by priority
}
