#include "memory_manager.hpp"
#include <algorithm>
#include <stdexcept>
#include <cmath>

// ─── Constructor ─────────────────────────────────────────────────────────────
MemoryManager::MemoryManager(int totalMB, int osReservedMB, int minSegmentMB,
                             int maxProcessMB, AllocationStrategy strategy, bool mmuEnabled)
    : totalMB_(totalMB), osReservedMB_(osReservedMB), minSegmentMB_(minSegmentMB),
      maxProcessMB_(maxProcessMB), strategy_(strategy), mmuEnabled_(mmuEnabled)
{
    // OS reserved block at address 0
    MemoryBlock osBlock;
    osBlock.startAddress = 0;
    osBlock.size         = osReservedMB;
    osBlock.isFree       = false;
    osBlock.pid          = std::nullopt;
    osBlock.segmentType  = SegmentType::OS;
    osBlock.label        = "SO";
    blocks_.push_back(osBlock);

    // One big free block for user processes
    MemoryBlock freeBlock;
    freeBlock.startAddress = osReservedMB;
    freeBlock.size         = totalMB - osReservedMB;
    freeBlock.isFree       = true;
    freeBlock.pid          = std::nullopt;
    freeBlock.segmentType  = SegmentType::FREE;
    freeBlock.label        = "Libre";
    blocks_.push_back(freeBlock);
}

// ─── roundUp ─────────────────────────────────────────────────────────────────
int MemoryManager::roundUp(int size) const {
    if (size <= 0) return minSegmentMB_;
    int r = ((size + minSegmentMB_ - 1) / minSegmentMB_) * minSegmentMB_;
    return std::max(r, minSegmentMB_);
}

// ─── findFreeBlock ────────────────────────────────────────────────────────────
std::list<MemoryBlock>::iterator MemoryManager::findFreeBlock(int size) {
    auto best = blocks_.end();

    for (auto it = blocks_.begin(); it != blocks_.end(); ++it) {
        if (!it->isFree || it->size < size) continue;

        switch (strategy_) {
            case AllocationStrategy::FIRST_FIT:
                return it;   // first hole that fits

            case AllocationStrategy::BEST_FIT:
                if (best == blocks_.end() || it->size < best->size)
                    best = it;
                break;

            case AllocationStrategy::WORST_FIT:
                if (best == blocks_.end() || it->size > best->size)
                    best = it;
                break;
        }
    }
    return best;
}

// ─── splitBlock ──────────────────────────────────────────────────────────────
void MemoryManager::splitBlock(std::list<MemoryBlock>::iterator it, int size,
                               int pid, const std::string& name, SegmentType seg)
{
    int remaining = it->size - size;
    it->isFree       = false;
    it->pid          = pid;
    it->size         = size;
    it->segmentType  = seg;
    it->label        = name + " [" + segmentTypeToString(seg) + "]";

    if (remaining >= minSegmentMB_) {
        MemoryBlock leftover;
        leftover.startAddress = it->startAddress + size;
        leftover.size         = remaining;
        leftover.isFree       = true;
        leftover.pid          = std::nullopt;
        leftover.segmentType  = SegmentType::FREE;
        leftover.label        = "Libre";
        auto next = it;
        ++next;
        blocks_.insert(next, leftover);
    }
}

// ─── mergeAdjacentFree ───────────────────────────────────────────────────────
void MemoryManager::mergeAdjacentFree() {
    auto it = blocks_.begin();
    while (it != blocks_.end()) {
        auto next = std::next(it);
        if (next == blocks_.end()) break;
        if (it->isFree && next->isFree) {
            it->size += next->size;
            blocks_.erase(next);
        } else {
            ++it;
        }
    }
}

// ─── allocate ────────────────────────────────────────────────────────────────
bool MemoryManager::allocate(int pid, const std::string& name, int memorySizeMB) {
    // Clamp to maxProcessMB
    int totalNeeded = std::min(memorySizeMB, maxProcessMB_);
    if (totalNeeded < minSegmentMB_) totalNeeded = minSegmentMB_;

    // Segment sizes (% of total, rounded up to minSegmentMB)
    int textSize  = roundUp(static_cast<int>(totalNeeded * 0.20));
    int dataSize  = roundUp(static_cast<int>(totalNeeded * 0.15));
    int heapSize  = roundUp(static_cast<int>(totalNeeded * 0.50));
    int stackSize = totalNeeded - textSize - dataSize - heapSize;
    if (stackSize < minSegmentMB_) stackSize = minSegmentMB_;

    struct Seg { SegmentType type; int size; };
    Seg segments[] = {
        { SegmentType::TEXT,  textSize  },
        { SegmentType::DATA,  dataSize  },
        { SegmentType::HEAP,  heapSize  },
        { SegmentType::STACK, stackSize }
    };

    // Check total available (contiguous not required per segment, but must fit each)
    for (auto& seg : segments) {
        if (findFreeBlock(seg.size) == blocks_.end()) return false;
    }

    int baseAddr = -1;

    // Allocate each segment
    for (auto& seg : segments) {
        auto it = findFreeBlock(seg.size);
        if (it == blocks_.end()) return false;  // should not happen (checked above)
        if (baseAddr < 0) baseAddr = it->startAddress;
        splitBlock(it, seg.size, pid, name, seg.type);
        mergeAdjacentFree();
    }

    // MMU entry
    if (mmuEnabled_) {
        MMUEntry entry;
        entry.pid          = pid;
        entry.logicalBase  = baseAddr;
        entry.physicalBase = baseAddr;
        entry.size         = totalNeeded;
        mmuTable_.push_back(entry);
    }

    return true;
}

// ─── free ────────────────────────────────────────────────────────────────────
void MemoryManager::free(int pid) {
    for (auto& block : blocks_) {
        if (block.pid == pid) {
            block.isFree       = true;
            block.pid          = std::nullopt;
            block.segmentType  = SegmentType::FREE;
            block.label        = "Libre";
        }
    }
    mergeAdjacentFree();

    // Remove MMU entry
    mmuTable_.erase(
        std::remove_if(mmuTable_.begin(), mmuTable_.end(),
                       [pid](const MMUEntry& e){ return e.pid == pid; }),
        mmuTable_.end());
}

// ─── stats ───────────────────────────────────────────────────────────────────
MemoryStats MemoryManager::stats() const {
    int used = 0, free = 0;
    int freeBlockCount = 0, totalNonOsBlocks = 0;

    for (const auto& b : blocks_) {
        if (b.segmentType == SegmentType::OS) continue;
        totalNonOsBlocks++;
        if (b.isFree) {
            free += b.size;
            freeBlockCount++;
        } else {
            used += b.size;
        }
    }

    double frag = 0.0;
    if (freeBlockCount > 1) {
        // Fragmentation = (free holes - 1) / total non-os blocks * 100
        frag = static_cast<double>(freeBlockCount - 1) /
               static_cast<double>(std::max(totalNonOsBlocks, 1)) * 100.0;
    }

    return { totalMB_, used, free, frag, strategyToString(strategy_) };
}

// ─── baseAddress ─────────────────────────────────────────────────────────────
int MemoryManager::baseAddress(int pid) const {
    for (const auto& e : mmuTable_) {
        if (e.pid == pid) return e.physicalBase;
    }
    // Fallback: search blocks
    for (const auto& b : blocks_) {
        if (b.pid == pid) return b.startAddress;
    }
    return -1;
}
