#pragma once

#include "paged_memory.hpp"
#include "page_table.hpp"
#include "page_replacer.hpp"
#include <memory>

class PagedMemoryManager {
public:
    PagedMemoryManager(int totalMemoryMB, int osReservedMB, int maxSwapMB, 
                       SwapDeviceType swapType, PageTableType ptType, 
                       ReplacementAlgorithm algo, int tlbSize);

    // Attempt to access a virtual page. 
    // Returns 0 if hit (RAM), > 0 if page fault (returns the penalty in ticks).
    // Returns -1 if memory access is invalid (e.g. OOM or unmapped without alloc right).
    int accessPage(int pid, int vpn, SegmentType type, unsigned int currentTick, bool write);

    // Allocate memory for a process. Returns true if successful.
    bool allocateProcess(int pid, int memorySizeMB, unsigned int currentTick);

    // Free all resources for a process (RAM, Swap, Page Table, TLB).
    void freeProcess(int pid);
    
    // Updates hardware bits periodically if needed (e.g., aging algorithm)
    void tick(unsigned int currentTick);

    const FrameTable& getFrameTable() const { return frameTable_; }
    const SwapManager& getSwapManager() const { return swapManager_; }
    TLB& getTLB() { return tlb_; }
    IPageTable& getPageTable() { return *pageTable_; }

private:
    FrameTable frameTable_;
    SwapManager swapManager_;
    TLB tlb_;
    std::unique_ptr<IPageTable> pageTable_;
    std::unique_ptr<IPageReplacer> replacer_;
    
    ReplacementAlgorithm algo_;
};
