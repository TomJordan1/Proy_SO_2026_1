#pragma once
#include "pcb.hpp"
#include "types.hpp"
#include <string>
#include <random>

// ─── Error Manager ───────────────────────────────────────────────────────────
// Randomly injects critical errors into running processes with configurable probability.
class ErrorManager {
public:
    explicit ErrorManager(double errorProbability);

    // Roll the dice for a running process. Returns true if an error occurred.
    // Also sets the error code on the PCB and marks it TERMINATED.
    bool tryInjectError(PCB& proc, int currentTick);

    // Total errors injected so far
    int errorCount() const { return errorCount_; }

    // Error rate as a percentage (errors / total calls * 100)
    double errorRate() const;

private:
    double probability_;       // e.g. 0.005 = 0.5%
    int    errorCount_  = 0;
    int    totalChecks_ = 0;
    std::mt19937 rng_;
    std::uniform_real_distribution<double> dist_;
    std::uniform_int_distribution<int>     codeDist_;

    ErrorCode randomErrorCode();
};
