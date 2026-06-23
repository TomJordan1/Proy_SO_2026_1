#pragma once

#include "types.hpp"
#include <vector>
#include <optional>
#include <unordered_map>
#include <list>

constexpr int PAGE_SIZE_KB = 4;
constexpr int PAGE_SIZE_BYTES = PAGE_SIZE_KB * 1024;

// ─── Frame ───────────────────────────────────────────────────────────────────
struct Frame {
    int index;
    bool isFree;
    std::optional<int> pid;
    int vpn; // Virtual Page Number mapped to this frame
    SegmentType segmentType;
    
    // Hardware bits (Managed by PagedMemoryManager/MMU)
    bool referenced;
    bool modified;
    
    // Metadata for some algorithms
    unsigned int loadTimeTick;
    unsigned int lastAccessTick;
    unsigned int agingCounter;
};

// ─── Frame Table ─────────────────────────────────────────────────────────────
class FrameTable {
public:
    FrameTable(int totalMemoryMB, int osReservedMB);

    int getTotalFrames() const { return totalFrames_; }
    int getFreeFramesCount() const { return freeFrames_; }
    
    // Allocate a free frame if available. Returns frame index or -1 if full.
    int allocateFrame(int pid, int vpn, SegmentType type, unsigned int currentTick);
    
    // Free a specific frame
    void freeFrame(int frameIndex);
    
    // Free all frames for a given process
    void freeProcessFrames(int pid);

    Frame* getFrame(int index);
    const std::vector<Frame>& getFrames() const { return frames_; }

private:
    std::vector<Frame> frames_;
    int totalFrames_;
    int freeFrames_;
    int osReservedFrames_;
};

// ─── Swap Page Record ────────────────────────────────────────────────────────
struct SwapPage {
    int pid;
    int vpn;
    SegmentType segmentType;
    bool modified; // If it was modified before being swapped out
};

// ─── Swap Manager ────────────────────────────────────────────────────────────
class SwapManager {
public:
    SwapManager(int maxSwapMB, SwapDeviceType type);

    // Latency getters
    int getReadLatencyTicks() const;
    int getWriteLatencyTicks() const;
    
    bool isFull() const;
    int getUsedPages() const { return usedPages_; }
    int getMaxPages() const { return maxPages_; }

    // Swap out a page to disk (from a frame). Returns true if successful.
    bool swapOut(int pid, int vpn, SegmentType type, bool modified);
    
    // Swap in a page from disk (to a frame). Removes from swap.
    bool swapIn(int pid, int vpn);
    
    // Free all swapped pages for a process
    void freeProcessSwap(int pid);

private:
    int maxPages_;
    int usedPages_;
    SwapDeviceType deviceType_;
    
    // Maps PID -> (VPN -> SwapPage)
    std::unordered_map<int, std::unordered_map<int, SwapPage>> swapStorage_;
};
