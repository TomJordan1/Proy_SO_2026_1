#include "io_manager.hpp"
#include <algorithm>
#include <random>
#include <cmath>

// ─── Static RNG ──────────────────────────────────────────────────────────────
static std::mt19937 ioRng(std::random_device{}());

// ─── Constructor ─────────────────────────────────────────────────────────────
IOManager::IOManager(const std::vector<IODeviceConfig>& configs, double freqMultiplier)
    : freqMultiplier_(freqMultiplier)
{
    for (const auto& cfg : configs) {
        IODevice dev;
        dev.id      = cfg.id;
        dev.latency = cfg.latency;
        devices_.push_back(dev);
    }
    // Ensure default devices exist if not provided
    auto hasDevice = [&](const std::string& id){
        for (const auto& d : devices_) if (d.id == id) return true;
        return false;
    };
    for (const char* id_cstr : {"KEYBOARD","DISK","PRINTER","NETWORK","USB"}) {
        const std::string id = id_cstr;
        if (!hasDevice(id)) {
            IODevice dev;
            dev.id      = id;
            dev.latency = 10;
            devices_.push_back(dev);
        }
    }
}

// ─── findDevice ──────────────────────────────────────────────────────────────
IODevice* IOManager::findDevice(const std::string& id) {
    for (auto& d : devices_) {
        if (d.id == id) return &d;
    }
    return nullptr;
}

// ─── startNext ───────────────────────────────────────────────────────────────
void IOManager::startNext(IODevice& dev) {
    if (dev.busy || dev.queue.empty()) return;
    dev.current = dev.queue.front();
    dev.queue.pop_front();
    dev.busy = true;
}

// ─── requestIO ───────────────────────────────────────────────────────────────
bool IOManager::requestIO(int pid, const std::string& processName, const std::string& deviceId) {
    IODevice* dev = findDevice(deviceId);
    if (!dev) return false;

    int ticks = static_cast<int>(std::ceil(dev->latency * freqMultiplier_));
    if (ticks < 1) ticks = 1;

    IORequest req;
    req.pid           = pid;
    req.processName   = processName;
    req.ticksRemaining = ticks;
    req.totalTicks    = ticks;

    if (!dev->busy) {
        dev->current = req;
        dev->busy    = true;
    } else {
        dev->queue.push_back(req);
    }
    return true;
}

// ─── cancelIO ────────────────────────────────────────────────────────────────
void IOManager::cancelIO(int pid) {
    for (auto& dev : devices_) {
        if (dev.busy && dev.current && dev.current->pid == pid) {
            dev.busy    = false;
            dev.current = std::nullopt;
            startNext(dev);
        }
        // Remove from queue
        dev.queue.erase(
            std::remove_if(dev.queue.begin(), dev.queue.end(),
                           [pid](const IORequest& r){ return r.pid == pid; }),
            dev.queue.end());
    }
}

// ─── tick ────────────────────────────────────────────────────────────────────
void IOManager::tick(std::function<void(int pid, const std::string& deviceId)> onComplete) {
    for (auto& dev : devices_) {
        if (!dev.busy || !dev.current) continue;

        dev.current->ticksRemaining--;

        if (dev.current->ticksRemaining <= 0) {
            // IO complete
            onComplete(dev.current->pid, dev.id);
            dev.busy    = false;
            dev.current = std::nullopt;
            startNext(dev);
        }
    }
}

// ─── randomInterrupt ─────────────────────────────────────────────────────────
bool IOManager::randomInterrupt(int pid, const std::string& processName,
                                int minDuration, int maxDuration)
{
    if (devices_.empty()) return false;

    std::uniform_int_distribution<int> devDist(0, (int)devices_.size() - 1);
    std::uniform_int_distribution<int> durDist(minDuration, maxDuration);

    IODevice& dev = devices_[devDist(ioRng)];
    int ticks = durDist(ioRng);

    IORequest req;
    req.pid            = pid;
    req.processName    = processName;
    req.ticksRemaining = ticks;
    req.totalTicks     = ticks;

    if (!dev.busy) {
        dev.current = req;
        dev.busy    = true;
    } else {
        dev.queue.push_back(req);
    }
    return true;
}

// ─── isWaiting ───────────────────────────────────────────────────────────────
bool IOManager::isWaiting(int pid) const {
    for (const auto& dev : devices_) {
        if (dev.busy && dev.current && dev.current->pid == pid) return true;
        for (const auto& r : dev.queue) {
            if (r.pid == pid) return true;
        }
    }
    return false;
}

// ─── waitingOn ───────────────────────────────────────────────────────────────
std::string IOManager::waitingOn(int pid) const {
    for (const auto& dev : devices_) {
        if (dev.busy && dev.current && dev.current->pid == pid) return dev.id;
        for (const auto& r : dev.queue) {
            if (r.pid == pid) return dev.id;
        }
    }
    return "";
}
