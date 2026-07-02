#include "paged_memory.hpp"
#include <algorithm>

// ─── Frame Table ─────────────────────────────────────────────────────────────

FrameTable::FrameTable(int totalMemoryMB, int osReservedMB) {
    totalFrames_ = (totalMemoryMB * 1024) / PAGE_SIZE_KB;
    osReservedFrames_ = (osReservedMB * 1024) / PAGE_SIZE_KB;
    
    // Total free initially is all minus OS reserved
    freeFrames_ = totalFrames_ - osReservedFrames_;

    frames_.resize(totalFrames_);
    for (int i = 0; i < totalFrames_; ++i) {
        frames_[i].index = i;
        if (i < osReservedFrames_) {
            frames_[i].isFree = false;
            frames_[i].pid = std::nullopt;
            frames_[i].segmentType = SegmentType::OS;
        } else {
            frames_[i].isFree = true;
            frames_[i].pid = std::nullopt;
            frames_[i].segmentType = SegmentType::FREE;
        }
        frames_[i].vpn = -1;
        frames_[i].referenced = false;
        frames_[i].modified = false;
        frames_[i].loadTimeTick = 0;
        frames_[i].lastAccessTick = 0;
        frames_[i].agingCounter = 0;
    }
}

int FrameTable::allocateFrame(int pid, int vpn, SegmentType type, unsigned int currentTick) {
    if (freeFrames_ == 0) return -1;

    for (int i = osReservedFrames_; i < totalFrames_; ++i) {
        if (frames_[i].isFree) {
            frames_[i].isFree = false;
            frames_[i].pid = pid;
            frames_[i].vpn = vpn;
            frames_[i].segmentType = type;
            frames_[i].referenced = true; // Implicitly referenced on load
            frames_[i].modified = false;
            frames_[i].loadTimeTick = currentTick;
            frames_[i].lastAccessTick = currentTick;
            frames_[i].agingCounter = 0;
            
            freeFrames_--;
            return i;
        }
    }
    return -1;
}

void FrameTable::freeFrame(int frameIndex) {
    if (frameIndex >= osReservedFrames_ && frameIndex < totalFrames_ && !frames_[frameIndex].isFree) {
        frames_[frameIndex].isFree = true;
        frames_[frameIndex].pid = std::nullopt;
        frames_[frameIndex].vpn = -1;
        frames_[frameIndex].segmentType = SegmentType::FREE;
        freeFrames_++;
    }
}

void FrameTable::freeProcessFrames(int pid) {
    for (int i = osReservedFrames_; i < totalFrames_; ++i) {
        if (!frames_[i].isFree && frames_[i].pid.has_value() && frames_[i].pid.value() == pid) {
            freeFrame(i);
        }
    }
}

Frame* FrameTable::getFrame(int index) {
    if (index >= 0 && index < totalFrames_) {
        return &frames_[index];
    }
    return nullptr;
}

// ─── Swap Manager ────────────────────────────────────────────────────────────

SwapManager::SwapManager(int maxSwapMB, SwapDeviceType type) : deviceType_(type) {
    maxPages_ = (maxSwapMB * 1024) / PAGE_SIZE_KB;
    usedPages_ = 0;
}

int SwapManager::getReadLatencyTicks() const {
    // HDD: ~15 ticks. SSD: ~3 ticks.
    return (deviceType_ == SwapDeviceType::HDD) ? 15 : 3;
}

int SwapManager::getWriteLatencyTicks() const {
    // SSDs might have asymmetric write latency due to erase cycles
    return (deviceType_ == SwapDeviceType::HDD) ? 15 : 5;
}

bool SwapManager::isFull() const {
    return usedPages_ >= maxPages_;
}

bool SwapManager::swapOut(int pid, int vpn, SegmentType type, bool modified) {
    if (isFull()) return false;
    
    SwapPage sp = {pid, vpn, type, modified};
    swapStorage_[pid][vpn] = sp;
    usedPages_++;
    return true;
}

bool SwapManager::swapIn(int pid, int vpn) {
    if (swapStorage_.count(pid) && swapStorage_[pid].count(vpn)) {
        swapStorage_[pid].erase(vpn);
        usedPages_--;
        if (swapStorage_[pid].empty()) {
            swapStorage_.erase(pid);
        }
        return true;
    }
    return false;
}

void SwapManager::freeProcessSwap(int pid) {
    if (swapStorage_.count(pid)) {
        usedPages_ -= swapStorage_[pid].size();
        swapStorage_.erase(pid);
    }
}
