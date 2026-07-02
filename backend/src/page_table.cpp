#include "page_table.hpp"

// ─── SingleLevelPT ───────────────────────────────────────────────────────────

void SingleLevelPT::mapPage(int pid, int vpn, int frameNumber, SegmentType type) {
    PTE pte;
    pte.valid = true;
    pte.frameNumber = frameNumber;
    pte.segmentType = type;
    tables_[pid][vpn] = pte;
}

void SingleLevelPT::unmapPage(int pid, int vpn) {
    if (tables_.count(pid)) {
        tables_[pid].erase(vpn);
    }
}

PTE* SingleLevelPT::lookup(int pid, int vpn) {
    if (tables_.count(pid) && tables_[pid].count(vpn)) {
        return &tables_[pid][vpn];
    }
    return nullptr;
}

void SingleLevelPT::freeProcess(int pid) {
    tables_.erase(pid);
}

// ─── TwoLevelPT ──────────────────────────────────────────────────────────────

void TwoLevelPT::mapPage(int pid, int vpn, int frameNumber, SegmentType type) {
    // Top 10 bits of 20-bit VPN is dir index, bottom 10 bits is pt index
    int dirIndex = (vpn >> 10) & 0x3FF;
    int ptIndex = vpn & 0x3FF;
    
    PTE pte;
    pte.valid = true;
    pte.frameNumber = frameNumber;
    pte.segmentType = type;
    
    directories_[pid].pt2[dirIndex][ptIndex] = pte;
}

void TwoLevelPT::unmapPage(int pid, int vpn) {
    if (directories_.count(pid)) {
        int dirIndex = (vpn >> 10) & 0x3FF;
        int ptIndex = vpn & 0x3FF;
        if (directories_[pid].pt2.count(dirIndex)) {
            directories_[pid].pt2[dirIndex].erase(ptIndex);
        }
    }
}

PTE* TwoLevelPT::lookup(int pid, int vpn) {
    if (directories_.count(pid)) {
        int dirIndex = (vpn >> 10) & 0x3FF;
        int ptIndex = vpn & 0x3FF;
        if (directories_[pid].pt2.count(dirIndex) && directories_[pid].pt2[dirIndex].count(ptIndex)) {
            return &directories_[pid].pt2[dirIndex][ptIndex];
        }
    }
    return nullptr;
}

void TwoLevelPT::freeProcess(int pid) {
    directories_.erase(pid);
}

// ─── InvertedPT ──────────────────────────────────────────────────────────────

InvertedPT::InvertedPT(int totalFrames) {
    table_.resize(totalFrames);
}

void InvertedPT::mapPage(int pid, int vpn, int frameNumber, SegmentType type) {
    if (frameNumber >= 0 && frameNumber < (int)table_.size()) {
        table_[frameNumber].pid = pid;
        table_[frameNumber].vpn = vpn;
        table_[frameNumber].pte.valid = true;
        table_[frameNumber].pte.frameNumber = frameNumber;
        table_[frameNumber].pte.segmentType = type;
    }
}

void InvertedPT::unmapPage(int pid, int vpn) {
    // Linear search is O(N), typical for inverted page tables without hash anchor
    for (auto& entry : table_) {
        if (entry.pid == pid && entry.vpn == vpn && entry.pte.valid) {
            entry.pte.valid = false;
            entry.pid = -1;
            entry.vpn = -1;
            break;
        }
    }
}

PTE* InvertedPT::lookup(int pid, int vpn) {
    for (auto& entry : table_) {
        if (entry.pid == pid && entry.vpn == vpn && entry.pte.valid) {
            return &entry.pte;
        }
    }
    return nullptr;
}

void InvertedPT::freeProcess(int pid) {
    for (auto& entry : table_) {
        if (entry.pid == pid) {
            entry.pte.valid = false;
            entry.pid = -1;
            entry.vpn = -1;
        }
    }
}

// ─── HashedPT ────────────────────────────────────────────────────────────────

HashedPT::HashedPT(int tableSize) : size_(tableSize) {
    table_.resize(size_);
}

int HashedPT::hashFunc(int pid, int vpn) const {
    unsigned int h = (pid * 31) ^ vpn;
    return h % size_;
}

void HashedPT::mapPage(int pid, int vpn, int frameNumber, SegmentType type) {
    int h = hashFunc(pid, vpn);
    for (auto& node : table_[h]) {
        if (node.pid == pid && node.vpn == vpn) {
            node.pte.valid = true;
            node.pte.frameNumber = frameNumber;
            node.pte.segmentType = type;
            return;
        }
    }
    PTE pte;
    pte.valid = true;
    pte.frameNumber = frameNumber;
    pte.segmentType = type;
    table_[h].push_back({pid, vpn, pte});
}

void HashedPT::unmapPage(int pid, int vpn) {
    int h = hashFunc(pid, vpn);
    auto it = table_[h].begin();
    while (it != table_[h].end()) {
        if (it->pid == pid && it->vpn == vpn) {
            it = table_[h].erase(it);
        } else {
            ++it;
        }
    }
}

PTE* HashedPT::lookup(int pid, int vpn) {
    int h = hashFunc(pid, vpn);
    for (auto& node : table_[h]) {
        if (node.pid == pid && node.vpn == vpn && node.pte.valid) {
            return &node.pte;
        }
    }
    return nullptr;
}

void HashedPT::freeProcess(int pid) {
    for (int i = 0; i < size_; ++i) {
        auto it = table_[i].begin();
        while (it != table_[i].end()) {
            if (it->pid == pid) {
                it = table_[i].erase(it);
            } else {
                ++it;
            }
        }
    }
}

// ─── TLB ─────────────────────────────────────────────────────────────────────

TLB::TLB(int size) : maxSize_(size), hits_(0), misses_(0) {}

int TLB::lookup(int pid, int vpn) {
    for (auto it = entries_.begin(); it != entries_.end(); ++it) {
        if (it->pid == pid && it->vpn == vpn) {
            // LRU: move to front
            TLBEntry entry = *it;
            entries_.erase(it);
            entries_.push_front(entry);
            hits_++;
            return entry.frameNumber;
        }
    }
    misses_++;
    return -1;
}

void TLB::insert(int pid, int vpn, int frameNumber) {
    // Remove if exists
    for (auto it = entries_.begin(); it != entries_.end(); ++it) {
        if (it->pid == pid && it->vpn == vpn) {
            entries_.erase(it);
            break;
        }
    }
    
    // If full, remove LRU (back)
    if ((int)entries_.size() >= maxSize_ && !entries_.empty()) {
        entries_.pop_back();
    }
    
    // If maxSize_ is 0, we effectively disable TLB by not inserting
    if (maxSize_ > 0) {
        // Insert at front (MRU)
        entries_.push_front({pid, vpn, frameNumber});
    }
}

void TLB::invalidate(int pid, int vpn) {
    for (auto it = entries_.begin(); it != entries_.end(); ++it) {
        if (it->pid == pid && it->vpn == vpn) {
            entries_.erase(it);
            break;
        }
    }
}

void TLB::invalidateProcess(int pid) {
    auto it = entries_.begin();
    while (it != entries_.end()) {
        if (it->pid == pid) {
            it = entries_.erase(it);
        } else {
            ++it;
        }
    }
}

void TLB::flush() {
    entries_.clear();
}
