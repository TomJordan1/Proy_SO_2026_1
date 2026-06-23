#pragma once

#include "paged_memory.hpp"
#include <vector>

class IPageReplacer {
public:
    virtual ~IPageReplacer() = default;

    // Called when a page fault occurs and we need a victim frame to replace.
    // Returns the frameIndex of the victim.
    virtual int selectVictim(FrameTable& ft, unsigned int currentTick) = 0;

    // Called when a frame is allocated or referenced, useful for updating data structures
    virtual void onPageReferenced(int frameIndex, unsigned int currentTick) = 0;

    // Called when a frame is freed (process terminates)
    virtual void onFrameFreed(int frameIndex) = 0;
};

// ─── FIFO ────────────────────────────────────────────────────────────────────
class FIFOReplacer : public IPageReplacer {
public:
    int selectVictim(FrameTable& ft, unsigned int currentTick) override;
    void onPageReferenced(int frameIndex, unsigned int currentTick) override;
    void onFrameFreed(int frameIndex) override;
private:
    std::vector<int> queue_;
};

// ─── LRU ─────────────────────────────────────────────────────────────────────
class LRUReplacer : public IPageReplacer {
public:
    int selectVictim(FrameTable& ft, unsigned int currentTick) override;
    void onPageReferenced(int frameIndex, unsigned int currentTick) override;
    void onFrameFreed(int frameIndex) override;
};

// ─── NRU ─────────────────────────────────────────────────────────────────────
class NRUReplacer : public IPageReplacer {
public:
    int selectVictim(FrameTable& ft, unsigned int currentTick) override;
    void onPageReferenced(int frameIndex, unsigned int currentTick) override;
    void onFrameFreed(int frameIndex) override;
};

// ─── Second Chance ───────────────────────────────────────────────────────────
class SecondChanceReplacer : public IPageReplacer {
public:
    int selectVictim(FrameTable& ft, unsigned int currentTick) override;
    void onPageReferenced(int frameIndex, unsigned int currentTick) override;
    void onFrameFreed(int frameIndex) override;
private:
    std::vector<int> queue_;
};

// ─── Clock ───────────────────────────────────────────────────────────────────
class ClockReplacer : public IPageReplacer {
public:
    ClockReplacer(int totalFrames);
    int selectVictim(FrameTable& ft, unsigned int currentTick) override;
    void onPageReferenced(int frameIndex, unsigned int currentTick) override;
    void onFrameFreed(int frameIndex) override;
private:
    int clockHand_ = 0;
    int totalFrames_;
};

// ─── NFU (Not Frequently Used) ───────────────────────────────────────────────
class NFUReplacer : public IPageReplacer {
public:
    int selectVictim(FrameTable& ft, unsigned int currentTick) override;
    void onPageReferenced(int frameIndex, unsigned int currentTick) override;
    void onFrameFreed(int frameIndex) override;
};

// ─── Aging ───────────────────────────────────────────────────────────────────
class AgingReplacer : public IPageReplacer {
public:
    int selectVictim(FrameTable& ft, unsigned int currentTick) override;
    void onPageReferenced(int frameIndex, unsigned int currentTick) override;
    void onFrameFreed(int frameIndex) override;
};

// ─── Working Set ─────────────────────────────────────────────────────────────
class WorkingSetReplacer : public IPageReplacer {
public:
    WorkingSetReplacer(unsigned int tau = 50); // Example tau
    int selectVictim(FrameTable& ft, unsigned int currentTick) override;
    void onPageReferenced(int frameIndex, unsigned int currentTick) override;
    void onFrameFreed(int frameIndex) override;
private:
    unsigned int tau_;
};

// ─── WSClock ─────────────────────────────────────────────────────────────────
class WSClockReplacer : public IPageReplacer {
public:
    WSClockReplacer(int totalFrames, unsigned int tau = 50);
    int selectVictim(FrameTable& ft, unsigned int currentTick) override;
    void onPageReferenced(int frameIndex, unsigned int currentTick) override;
    void onFrameFreed(int frameIndex) override;
private:
    int clockHand_ = 0;
    int totalFrames_;
    unsigned int tau_;
};
