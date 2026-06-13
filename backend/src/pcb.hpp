#pragma once
#include "types.hpp"
#include <string>
#include <optional>

// ─── Registers saved during context switch ──────────────────────────────────
struct Registers {
    int AX = 0, BX = 0, CX = 0, DX = 0;
};

// ─── Process Control Block ───────────────────────────────────────────────────
struct PCB {
    // Identity
    int         pid;
    std::string name;
    ProcessType type;

    // State
    ProcessState state       = ProcessState::NEW;

    // CPU context
    int         pc           = 0;   // Program Counter (logical, in ticks/instructions)
    Registers   registers;

    // Scheduling info
    int         priority;
    int         burstTime;
    int         remainingTime;
    int         quantumUsed  = 0;

    // MLFQ level (0 = highest)
    int         mlfqLevel    = 0;

    // Timing
    int         arrivalTick  = 0;
    int         waitingTime  = 0;
    int         responseTime = -1;  // -1 = not yet responded
    int         startTick    = -1;  // first time it entered RUNNING
    int         finishTick   = -1;
    int         turnaround   = 0;

    // Memory
    int         memorySizeMB        = 0;
    int         memoryBaseAddress   = 0;  // physical base in MB
    int         stackPointer        = 0;
    int         heapPointer         = 0;

    // I/O
    std::optional<std::string> ioDevice;   // device being waited on
    int         ioRemainingTicks = 0;

    // Error
    ErrorCode   errorCode    = ErrorCode::NONE;

    // CPU assignment
    std::optional<int> cpuId;

    // ── Helpers ──────────────────────────────────────────────────────────────
    double completionPercent() const {
        if (burstTime == 0) return 100.0;
        double done = static_cast<double>(burstTime - remainingTime);
        return (done / burstTime) * 100.0;
    }

    std::string pcHex() const {
        char buf[12];
        snprintf(buf, sizeof(buf), "0x%04X", pc & 0xFFFF);
        return std::string(buf);
    }

    bool isAlive() const {
        return state != ProcessState::TERMINATED;
    }
};
