#pragma once
#include <optional>
#include <string>
#include <vector>

// ─── Process States ─────────────────────────────────────────────────────────
enum class ProcessState { NEW, READY, RUNNING, WAITING, TERMINATED, ERROR, SUSPENDED };

inline std::string stateToString(ProcessState s) {
    switch (s) {
        case ProcessState::NEW:
            return "NEW";
        case ProcessState::READY:
            return "READY";
        case ProcessState::RUNNING:
            return "RUNNING";
        case ProcessState::WAITING:
            return "WAITING";
        case ProcessState::TERMINATED:
            return "TERMINATED";
        case ProcessState::ERROR:
            return "ERROR";
        case ProcessState::SUSPENDED:
            return "SUSPENDED";
    }
    return "UNKNOWN";
}

// ─── Process Types ───────────────────────────────────────────────────────────
enum class ProcessType { SYSTEM, CPU_BOUND, INTERACTIVE, IO_BOUND };

inline std::string processTypeToString(ProcessType t) {
    switch (t) {
        case ProcessType::SYSTEM:
            return "SYSTEM";
        case ProcessType::CPU_BOUND:
            return "CPU_BOUND";
        case ProcessType::INTERACTIVE:
            return "INTERACTIVE";
        case ProcessType::IO_BOUND:
            return "IO_BOUND";
    }
    return "UNKNOWN";
}

inline std::string processTypeLabel(ProcessType t) {
    switch (t) {
        case ProcessType::SYSTEM:
            return "SYS";
        case ProcessType::CPU_BOUND:
            return "CPU";
        case ProcessType::INTERACTIVE:
            return "INT";
        case ProcessType::IO_BOUND:
            return "IO";
    }
    return "?";
}

inline ProcessType parseProcessType(const std::string &s) {
    if (s == "SYSTEM") return ProcessType::SYSTEM;
    if (s == "CPU_BOUND") return ProcessType::CPU_BOUND;
    if (s == "INTERACTIVE") return ProcessType::INTERACTIVE;
    if (s == "IO_BOUND") return ProcessType::IO_BOUND;
    return ProcessType::CPU_BOUND;
}

// ─── Scheduler Algorithms ───────────────────────────────────────────────────
enum class SchedulerAlgo { FCFS, SJF, SRTF, PRIORITY, RR, MLFQ };

inline SchedulerAlgo parseAlgo(const std::string &s) {
    if (s == "FCFS") return SchedulerAlgo::FCFS;
    if (s == "SJF") return SchedulerAlgo::SJF;
    if (s == "SRTF") return SchedulerAlgo::SRTF;
    if (s == "Priority") return SchedulerAlgo::PRIORITY;
    if (s == "PRIORITY") return SchedulerAlgo::PRIORITY;
    if (s == "RR") return SchedulerAlgo::RR;
    if (s == "ROUND_ROBIN") return SchedulerAlgo::RR;
    if (s == "MLFQ") return SchedulerAlgo::MLFQ;
    return SchedulerAlgo::FCFS;
}

inline std::string algoToString(SchedulerAlgo a) {
    switch (a) {
        case SchedulerAlgo::FCFS:
            return "FCFS";
        case SchedulerAlgo::SJF:
            return "SJF";
        case SchedulerAlgo::SRTF:
            return "SRTF";
        case SchedulerAlgo::PRIORITY:
            return "Priority";
        case SchedulerAlgo::RR:
            return "RR";
        case SchedulerAlgo::MLFQ:
            return "MLFQ";
    }
    return "FCFS";
}

// ─── Memory Allocation Strategies ───────────────────────────────────────────
enum class AllocationStrategy { FIRST_FIT, BEST_FIT, WORST_FIT };

inline AllocationStrategy parseStrategy(const std::string &s) {
    if (s == "BEST_FIT") return AllocationStrategy::BEST_FIT;
    if (s == "WORST_FIT") return AllocationStrategy::WORST_FIT;
    return AllocationStrategy::FIRST_FIT;
}

inline std::string strategyToString(AllocationStrategy s) {
    switch (s) {
        case AllocationStrategy::FIRST_FIT:
            return "First Fit";
        case AllocationStrategy::BEST_FIT:
            return "Best Fit";
        case AllocationStrategy::WORST_FIT:
            return "Worst Fit";
    }
    return "First Fit";
}

// ─── Segment Types ───────────────────────────────────────────────────────────
enum class SegmentType { OS, TEXT, DATA, HEAP, STACK, FREE };

inline std::string segmentTypeToString(SegmentType t) {
    switch (t) {
        case SegmentType::OS: return "OS";
        case SegmentType::TEXT: return "TEXT";
        case SegmentType::DATA: return "DATA";
        case SegmentType::HEAP: return "HEAP";
        case SegmentType::STACK: return "STACK";
        case SegmentType::FREE: return "FREE";
    }
    return "FREE";
}

// ─── Virtual Memory Enums ────────────────────────────────────────────────────
enum class MemoryMode { CONTIGUOUS, PAGED };

inline MemoryMode parseMemoryMode(const std::string &s) {
    if (s == "PAGED") return MemoryMode::PAGED;
    return MemoryMode::CONTIGUOUS;
}

enum class PageTableType { SINGLE_LEVEL, TWO_LEVEL, INVERTED, HASHED };

inline PageTableType parsePageTableType(const std::string &s) {
    if (s == "TWO_LEVEL") return PageTableType::TWO_LEVEL;
    if (s == "INVERTED") return PageTableType::INVERTED;
    if (s == "HASHED") return PageTableType::HASHED;
    return PageTableType::SINGLE_LEVEL;
}

enum class SwapDeviceType { HDD, SSD };

inline SwapDeviceType parseSwapDeviceType(const std::string &s) {
    if (s == "SSD") return SwapDeviceType::SSD;
    return SwapDeviceType::HDD;
}

enum class ReplacementAlgorithm {
    NRU, FIFO, SECOND_CHANCE, CLOCK, LRU, NFU, AGING, WORKING_SET, WSCLOCK
};

inline ReplacementAlgorithm parseReplacementAlgorithm(const std::string &s) {
    if (s == "NRU") return ReplacementAlgorithm::NRU;
    if (s == "FIFO") return ReplacementAlgorithm::FIFO;
    if (s == "SECOND_CHANCE") return ReplacementAlgorithm::SECOND_CHANCE;
    if (s == "CLOCK") return ReplacementAlgorithm::CLOCK;
    if (s == "LRU") return ReplacementAlgorithm::LRU;
    if (s == "NFU") return ReplacementAlgorithm::NFU;
    if (s == "AGING") return ReplacementAlgorithm::AGING;
    if (s == "WORKING_SET") return ReplacementAlgorithm::WORKING_SET;
    if (s == "WSCLOCK") return ReplacementAlgorithm::WSCLOCK;
    return ReplacementAlgorithm::FIFO;
}

inline std::string replacementAlgoToString(ReplacementAlgorithm a) {
    switch (a) {
        case ReplacementAlgorithm::NRU: return "NRU";
        case ReplacementAlgorithm::FIFO: return "FIFO";
        case ReplacementAlgorithm::SECOND_CHANCE: return "SECOND_CHANCE";
        case ReplacementAlgorithm::CLOCK: return "CLOCK";
        case ReplacementAlgorithm::LRU: return "LRU";
        case ReplacementAlgorithm::NFU: return "NFU";
        case ReplacementAlgorithm::AGING: return "AGING";
        case ReplacementAlgorithm::WORKING_SET: return "WORKING_SET";
        case ReplacementAlgorithm::WSCLOCK: return "WSCLOCK";
    }
    return "FIFO";
}

// ─── Memory Access Pattern ───────────────────────────────────────────────────
enum class MemoryAccessPattern { SEQUENTIAL, LOCALITY };

inline std::string accessPatternToString(MemoryAccessPattern p) {
    switch (p) {
        case MemoryAccessPattern::SEQUENTIAL: return "SEQUENTIAL";
        case MemoryAccessPattern::LOCALITY: return "LOCALITY";
    }
    return "SEQUENTIAL";
}

// ─── Error Codes ─────────────────────────────────────────────────────────────
enum class ErrorCode { NONE, SEGFAULT, DIV_ZERO, OVERFLOW_ERROR, ILLEGAL_ACCESS, CANCEL_USR };

inline std::string errorCodeToString(ErrorCode e) {
    switch (e) {
        case ErrorCode::NONE:
            return "";
        case ErrorCode::SEGFAULT:
            return "SEGFAULT";
        case ErrorCode::DIV_ZERO:
            return "DIV_ZERO";
        case ErrorCode::OVERFLOW_ERROR:
            return "OVERFLOW_ERROR";
        case ErrorCode::ILLEGAL_ACCESS:
            return "ILLEGAL_ACCESS";
        case ErrorCode::CANCEL_USR:
            return "CANCEL_USR";
    }
    return "";
}

// ─── IO Error Codes ──────────────────────────────────────────────────────────
enum class IOErrorCode { NONE, TIMEOUT, DEVICE_OFFLINE, CORRUPTED_DATA, PERMISSION_DENIED };

inline std::string ioErrorCodeToString(IOErrorCode e) {
    switch (e) {
        case IOErrorCode::NONE: return "";
        case IOErrorCode::TIMEOUT: return "TIMEOUT";
        case IOErrorCode::DEVICE_OFFLINE: return "DEVICE_OFFLINE";
        case IOErrorCode::CORRUPTED_DATA: return "CORRUPTED_DATA";
        case IOErrorCode::PERMISSION_DENIED: return "PERMISSION_DENIED";
    }
    return "";
}

// ─── Simulation Event (from input JSON) ─────────────────────────────────────
struct SimEvent {
    int tick;
    std::string type; // device id
    int pid;
    std::string action; // CANCEL, WAIT_FOR_SIGNAL, etc.
};

// ─── IO Device Config (from input JSON) ──────────────────────────────────────
struct IODeviceConfig {
    std::string id;
    int latency;
};

// ─── Simulation Configuration ────────────────────────────────────────────────
struct SimConfig {
    // Metadata
    std::string name;
    std::string executionDate;
    std::string executionTime;

    // CPU
    int numCores = 1;
    SchedulerAlgo scheduler = SchedulerAlgo::FCFS;
    bool preemptive = false;
    int quantum = 4;
    int contextSwitchCost = 1;

    // Memory
    int totalMemoryMB = 1024;
    int osReservedMB = 64;
    int minSegmentMB = 4;
    int maxProcessMB = 256;
    AllocationStrategy strategy = AllocationStrategy::FIRST_FIT;
    bool mmuEnabled = true;

    // Virtual Memory (Paging)
    MemoryMode memoryMode = MemoryMode::CONTIGUOUS;
    PageTableType pageTableType = PageTableType::SINGLE_LEVEL;
    SwapDeviceType swapDeviceType = SwapDeviceType::HDD;
    ReplacementAlgorithm replacementAlgorithm = ReplacementAlgorithm::FIFO;
    int tlbSize = 16;
    int swapSizeMB = 2048;

    // IO Devices
    std::vector<IODeviceConfig> ioDevices;

    // Simulation params
    int speedMS = 100;
    double errorProbability = 0.005;
    double ioFreqMultiplier = 1.0;
    bool agingEnabled = false;
    int agingInterval = 20;
    bool autoCreate = false;
    int autoCreateMaxTicks = 0;
    double cpuBoundRatio = 0.5;

    // Events
    std::vector<SimEvent> events;
};

// ─── Process definition from input ─────────────────────────────────────────
struct ProcessDef {
    std::string name;
    int burst_time;
    int priority;
    int memory_size;
    std::string process_type;
    int arrival_tick;
};
