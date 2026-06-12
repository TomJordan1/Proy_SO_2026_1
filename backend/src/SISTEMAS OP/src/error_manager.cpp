#include "error_manager.hpp"

// ─── Constructor ─────────────────────────────────────────────────────────────
ErrorManager::ErrorManager(double errorProbability)
    : probability_(errorProbability),
      rng_(std::random_device{}()),
      dist_(0.0, 1.0),
      codeDist_(1, 4)   // maps to ErrorCode enum values 1..4
{}

// ─── tryInjectError ──────────────────────────────────────────────────────────
bool ErrorManager::tryInjectError(PCB& proc, int currentTick) {
    (void)currentTick;
    ++totalChecks_;

    if (dist_(rng_) < probability_) {
        ++errorCount_;
        proc.errorCode  = randomErrorCode();
        proc.state      = ProcessState::TERMINATED;
        proc.finishTick = currentTick;
        proc.turnaround = currentTick - proc.arrivalTick;
        proc.cpuId      = std::nullopt;
        return true;
    }
    return false;
}

// ─── errorRate ───────────────────────────────────────────────────────────────
double ErrorManager::errorRate() const {
    if (totalChecks_ == 0) return 0.0;
    return (static_cast<double>(errorCount_) / totalChecks_) * 100.0;
}

// ─── randomErrorCode ─────────────────────────────────────────────────────────
ErrorCode ErrorManager::randomErrorCode() {
    switch (codeDist_(rng_)) {
        case 1: return ErrorCode::SEGFAULT;
        case 2: return ErrorCode::DIV_ZERO;
        case 3: return ErrorCode::OVERFLOW;
        case 4: return ErrorCode::ILLEGAL_ACCESS;
        default: return ErrorCode::SEGFAULT;
    }
}
