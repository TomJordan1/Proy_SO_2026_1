#pragma once
#include "pcb.hpp"
#include "types.hpp"
#include <string>
#include <deque>
#include <vector>
#include <optional>
#include <functional>

// ─── IO Request ──────────────────────────────────────────────────────────────
struct IORequest {
    int pid;
    std::string processName;
    int ticksRemaining;
    int totalTicks;
};

// ─── IO Device ───────────────────────────────────────────────────────────────
struct IODevice {
    std::string         id;
    int                 latency;           // base latency in ticks
    bool                busy    = false;
    std::optional<IORequest> current;
    std::deque<IORequest>    queue;

    // Snapshot fields
    std::string status()         const { return busy ? "BUSY" : "IDLE"; }
    double progressPercent()     const {
        if (!current || current->totalTicks == 0) return 0.0;
        double done = current->totalTicks - current->ticksRemaining;
        return (done / current->totalTicks) * 100.0;
    }
    std::vector<int> queuePids() const {
        std::vector<int> pids;
        for (const auto& r : queue) pids.push_back(r.pid);
        return pids;
    }
    int queueLength() const { return (int)queue.size(); }
};

// ─── IO Manager ──────────────────────────────────────────────────────────────
class IOManager {
public:
    // Initialize with the device configs from the JSON
    explicit IOManager(const std::vector<IODeviceConfig>& configs, double freqMultiplier = 1.0);

    // Enqueue an IO request for a process on a given device.
    // Returns false if the device id is not found.
    bool requestIO(int pid, const std::string& processName, const std::string& deviceId);

    // Cancel any pending IO for a process (used for CANCEL events).
    void cancelIO(int pid);

    // Advance all devices by one tick.
    // Calls 'onComplete' for each process whose IO has finished.
    void tick(std::function<void(int pid, const std::string& deviceId)> onComplete);

    // Generate a random IO interruption for a process on a random device
    // (between minDuration and maxDuration ticks).
    bool randomInterrupt(int pid, const std::string& processName,
                         int minDuration, int maxDuration);

    const std::vector<IODevice>& devices() const { return devices_; }
    std::vector<IODevice>&       devices()       { return devices_; }

    // Check if a specific pid is waiting on any device
    bool isWaiting(int pid) const;

    // Return which device a pid is waiting on (empty if none)
    std::string waitingOn(int pid) const;

private:
    std::vector<IODevice> devices_;
    double freqMultiplier_;

    IODevice* findDevice(const std::string& id);
    void startNext(IODevice& dev);
};
