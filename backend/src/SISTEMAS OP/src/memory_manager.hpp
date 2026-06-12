#pragma once
#include "types.hpp"
#include <vector>
#include <list>
#include <optional>
#include <string>

// ─── Memory Block ─────────────────────────────────────────────────────────────
struct MemoryBlock {
    int         startAddress;   // MB offset from address 0
    int         size;           // in MB
    bool        isFree;
    std::optional<int> pid;
    SegmentType segmentType     = SegmentType::FREE;
    std::string label;
};

// ─── MMU Entry ───────────────────────────────────────────────────────────────
struct MMUEntry {
    int pid;
    int logicalBase;
    int physicalBase;
    int size;
};

// ─── Memory Snapshot ─────────────────────────────────────────────────────────
struct MemoryStats {
    int    totalMB;
    int    usedMB;
    int    freeMB;
    double fragmentationPercent;
    std::string strategy;
};

// ─── Memory Manager ──────────────────────────────────────────────────────────
class MemoryManager {
public:
    MemoryManager(int totalMB, int osReservedMB, int minSegmentMB,
                  int maxProcessMB, AllocationStrategy strategy, bool mmuEnabled);

    // Try to allocate memory for a process.
    // Segments: TEXT(20%), DATA(15%), HEAP(50%), STACK(15%)
    // Returns true if allocation succeeded.
    bool allocate(int pid, const std::string& name, int memorySizeMB);

    // Free all memory blocks belonging to a process.
    void free(int pid);

    // Snapshot accessors
    MemoryStats               stats() const;
    const std::list<MemoryBlock>& blocks() const { return blocks_; }
    const std::vector<MMUEntry>&  mmuTable() const { return mmuTable_; }

    // Returns the base address assigned to a pid, or -1 if not found.
    int baseAddress(int pid) const;

    AllocationStrategy strategy() const { return strategy_; }

private:
    int totalMB_;
    int osReservedMB_;
    int minSegmentMB_;
    int maxProcessMB_;
    AllocationStrategy strategy_;
    bool mmuEnabled_;

    std::list<MemoryBlock> blocks_;
    std::vector<MMUEntry>  mmuTable_;

    // Find a free block to fit `size` MB using the configured strategy.
    std::list<MemoryBlock>::iterator findFreeBlock(int size);

    // Split a free block if it's larger than needed.
    void splitBlock(std::list<MemoryBlock>::iterator it, int size,
                    int pid, const std::string& name, SegmentType seg);

    // Merge adjacent free blocks (defragmentation step).
    void mergeAdjacentFree();

    // Round up to minSegmentMB
    int roundUp(int size) const;
};
