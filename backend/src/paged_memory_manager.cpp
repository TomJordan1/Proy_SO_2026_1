#include "paged_memory_manager.hpp"

PagedMemoryManager::PagedMemoryManager(int totalMemoryMB, int osReservedMB, int maxSwapMB, 
                                       SwapDeviceType swapType, PageTableType ptType, 
                                       ReplacementAlgorithm algo, int tlbSize)
    : frameTable_(totalMemoryMB, osReservedMB), 
      swapManager_(maxSwapMB, swapType), 
      tlb_(tlbSize), 
      algo_(algo) 
{
    switch(ptType) {
        case PageTableType::SINGLE_LEVEL: pageTable_ = std::make_unique<SingleLevelPT>(); break;
        case PageTableType::TWO_LEVEL: pageTable_ = std::make_unique<TwoLevelPT>(); break;
        case PageTableType::INVERTED: pageTable_ = std::make_unique<InvertedPT>(frameTable_.getTotalFrames()); break;
        case PageTableType::HASHED: pageTable_ = std::make_unique<HashedPT>(); break;
    }

    switch(algo) {
        case ReplacementAlgorithm::FIFO: replacer_ = std::make_unique<FIFOReplacer>(); break;
        case ReplacementAlgorithm::LRU: replacer_ = std::make_unique<LRUReplacer>(); break;
        case ReplacementAlgorithm::NRU: replacer_ = std::make_unique<NRUReplacer>(); break;
        case ReplacementAlgorithm::SECOND_CHANCE: replacer_ = std::make_unique<SecondChanceReplacer>(); break;
        case ReplacementAlgorithm::CLOCK: replacer_ = std::make_unique<ClockReplacer>(frameTable_.getTotalFrames()); break;
        case ReplacementAlgorithm::NFU: replacer_ = std::make_unique<NFUReplacer>(); break;
        case ReplacementAlgorithm::AGING: replacer_ = std::make_unique<AgingReplacer>(); break;
        case ReplacementAlgorithm::WORKING_SET: replacer_ = std::make_unique<WorkingSetReplacer>(); break;
        case ReplacementAlgorithm::WSCLOCK: replacer_ = std::make_unique<WSClockReplacer>(frameTable_.getTotalFrames()); break;
    }
}

bool PagedMemoryManager::allocateProcess(int pid, int memorySizeMB, unsigned int currentTick) {
    int pagesNeeded = (memorySizeMB * 1024) / PAGE_SIZE_KB;
    // We don't eagerly allocate frames in demand paging, 
    // but we can check if total pages (RAM+Swap) exceeds system capacity.
    int availableCapacity = frameTable_.getFreeFramesCount() + (swapManager_.getMaxPages() - swapManager_.getUsedPages());
    if (pagesNeeded > availableCapacity) {
        return false; // Out of memory
    }
    return true; // Actual allocation happens on demand via Page Faults
}

int PagedMemoryManager::accessPage(int pid, int vpn, SegmentType type, unsigned int currentTick, bool write) {
    // 1. Check TLB
    int frame = tlb_.lookup(pid, vpn);
    if (frame != -1) {
        // TLB Hit
        Frame* f = frameTable_.getFrame(frame);
        if (f) {
            f->referenced = true;
            if (write) f->modified = true;
            f->lastAccessTick = currentTick;
            replacer_->onPageReferenced(frame, currentTick);
        }
        return 0; // 0 penalty
    }

    // 2. TLB Miss -> Check Page Table
    PTE* pte = pageTable_->lookup(pid, vpn);
    if (pte && pte->valid) {
        // PT Hit (Page is in RAM, just wasn't in TLB)
        frame = pte->frameNumber;
        tlb_.insert(pid, vpn, frame);
        
        Frame* f = frameTable_.getFrame(frame);
        if (f) {
            f->referenced = true;
            if (write) f->modified = true;
            f->lastAccessTick = currentTick;
            replacer_->onPageReferenced(frame, currentTick);
        }
        return 1; // Small penalty for PT walk
    }

    // 3. Page Fault (Page not in RAM)
    // We need to load it. Maybe it's in Swap, or maybe it's first time access.
    bool fromSwap = swapManager_.swapIn(pid, vpn);
    int penalty = fromSwap ? swapManager_.getReadLatencyTicks() : 3; // Disks are extremely slow, so penalty is high.

    // 4. Find free frame or replace
    frame = frameTable_.allocateFrame(pid, vpn, type, currentTick);
    if (frame == -1) {
        // Need to replace
        int victimFrame = replacer_->selectVictim(frameTable_, currentTick);
        if (victimFrame == -1) {
            return -1; // OOM, swap is full or no replacable pages
        }
        
        Frame* victim = frameTable_.getFrame(victimFrame);
        // Swap out victim
        if (!swapManager_.swapOut(victim->pid.value(), victim->vpn, victim->segmentType, victim->modified)) {
             return -1; // Swap full
        }
        penalty += swapManager_.getWriteLatencyTicks();
        
        // Unmap victim from PT and TLB
        pageTable_->unmapPage(victim->pid.value(), victim->vpn);
        tlb_.invalidate(victim->pid.value(), victim->vpn);
        replacer_->onFrameFreed(victimFrame);
        
        // Free frame physically then re-allocate
        frameTable_.freeFrame(victimFrame);
        frame = frameTable_.allocateFrame(pid, vpn, type, currentTick);
    }
    
    // 5. Update PT and TLB with new frame
    pageTable_->mapPage(pid, vpn, frame, type);
    tlb_.insert(pid, vpn, frame);
    
    Frame* f = frameTable_.getFrame(frame);
    if (f) {
        if (write) f->modified = true;
        replacer_->onPageReferenced(frame, currentTick);
    }

    return penalty;
}

void PagedMemoryManager::freeProcess(int pid) {
    // Notify replacer
    const auto& frames = frameTable_.getFrames();
    for (int i = 0; i < (int)frames.size(); ++i) {
        if (!frames[i].isFree && frames[i].pid == pid) {
            replacer_->onFrameFreed(i);
        }
    }
    
    frameTable_.freeProcessFrames(pid);
    swapManager_.freeProcessSwap(pid);
    pageTable_->freeProcess(pid);
    tlb_.invalidateProcess(pid);
}

void PagedMemoryManager::tick(unsigned int currentTick) {
    if (algo_ == ReplacementAlgorithm::AGING) {
        const auto& frames = frameTable_.getFrames();
        for (int i = 0; i < (int)frames.size(); ++i) {
            if (!frames[i].isFree && frames[i].segmentType != SegmentType::OS) {
                Frame* f = frameTable_.getFrame(i);
                f->agingCounter >>= 1;
                if (f->referenced) {
                    f->agingCounter |= (1 << 31);
                    f->referenced = false; // Reset R bit after tick
                }
            }
        }
    }
}
