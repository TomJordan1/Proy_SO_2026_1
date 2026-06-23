#pragma once

#include "types.hpp"
#include <vector>
#include <unordered_map>
#include <list>
#include <optional>

// ─── PTE (Page Table Entry) ──────────────────────────────────────────────────
struct PTE {
    bool valid = false;
    int frameNumber = -1;
    SegmentType segmentType = SegmentType::FREE;
    // We store R and M bits directly in the Frame to have a unified place for 
    // replacement algorithms to check, but logically they belong to the PTE.
    // In our simulation, valid=true means it's in RAM.
};

// ─── IPageTable Interface ────────────────────────────────────────────────────
class IPageTable {
public:
    virtual ~IPageTable() = default;
    
    // Map a virtual page to a physical frame
    virtual void mapPage(int pid, int vpn, int frameNumber, SegmentType type) = 0;
    
    // Unmap a virtual page
    virtual void unmapPage(int pid, int vpn) = 0;
    
    // Look up a VPN. Returns a pointer to the PTE if found, nullptr otherwise.
    virtual PTE* lookup(int pid, int vpn) = 0;
    
    // Free all pages for a process
    virtual void freeProcess(int pid) = 0;
};

// ─── SingleLevelPT ───────────────────────────────────────────────────────────
class SingleLevelPT : public IPageTable {
public:
    void mapPage(int pid, int vpn, int frameNumber, SegmentType type) override;
    void unmapPage(int pid, int vpn) override;
    PTE* lookup(int pid, int vpn) override;
    void freeProcess(int pid) override;
private:
    // pid -> (vpn -> PTE) (Using a map to simulate a large 1D array per process sparsely to save host memory)
    std::unordered_map<int, std::unordered_map<int, PTE>> tables_;
};

// ─── TwoLevelPT ──────────────────────────────────────────────────────────────
class TwoLevelPT : public IPageTable {
public:
    void mapPage(int pid, int vpn, int frameNumber, SegmentType type) override;
    void unmapPage(int pid, int vpn) override;
    PTE* lookup(int pid, int vpn) override;
    void freeProcess(int pid) override;
private:
    struct Directory {
        std::unordered_map<int, std::unordered_map<int, PTE>> pt2; // dir_index -> (pt_index -> PTE)
    };
    std::unordered_map<int, Directory> directories_;
};

// ─── InvertedPT ──────────────────────────────────────────────────────────────
class InvertedPT : public IPageTable {
public:
    InvertedPT(int totalFrames);
    void mapPage(int pid, int vpn, int frameNumber, SegmentType type) override;
    void unmapPage(int pid, int vpn) override;
    PTE* lookup(int pid, int vpn) override;
    void freeProcess(int pid) override;
private:
    struct InvertedEntry {
        int pid = -1;
        int vpn = -1;
        PTE pte;
    };
    std::vector<InvertedEntry> table_; // Indexed by Frame Number
};

// ─── HashedPT ────────────────────────────────────────────────────────────────
class HashedPT : public IPageTable {
public:
    HashedPT(int tableSize = 10007);
    void mapPage(int pid, int vpn, int frameNumber, SegmentType type) override;
    void unmapPage(int pid, int vpn) override;
    PTE* lookup(int pid, int vpn) override;
    void freeProcess(int pid) override;
private:
    struct HashNode {
        int pid;
        int vpn;
        PTE pte;
    };
    int size_;
    std::vector<std::list<HashNode>> table_;
    int hashFunc(int pid, int vpn) const;
};

// ─── TLB (Translation Lookaside Buffer) ──────────────────────────────────────
struct TLBEntry {
    int pid;
    int vpn;
    int frameNumber;
};

class TLB {
public:
    TLB(int size);
    
    // Returns frame number if hit, -1 if miss
    int lookup(int pid, int vpn);
    
    // Insert or update an entry
    void insert(int pid, int vpn, int frameNumber);
    
    // Invalidate a specific entry
    void invalidate(int pid, int vpn);
    
    // Invalidate all entries for a process
    void invalidateProcess(int pid);
    
    // Flush the entire TLB
    void flush();
    
    // Metrics
    int getHits() const { return hits_; }
    int getMisses() const { return misses_; }

    const std::list<TLBEntry>& getEntries() const { return entries_; }

private:
    int maxSize_;
    int hits_;
    int misses_;
    
    // LRU mechanism for TLB entries
    std::list<TLBEntry> entries_;
};
