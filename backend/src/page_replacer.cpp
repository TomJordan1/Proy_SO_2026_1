#include "page_replacer.hpp"
#include <algorithm>
#include <climits>

// ─── FIFO ────────────────────────────────────────────────────────────────────
int FIFOReplacer::selectVictim(FrameTable& ft, unsigned int currentTick) {
    if (queue_.empty()) return -1;
    int victim = queue_.front();
    queue_.erase(queue_.begin());
    return victim;
}

void FIFOReplacer::onPageReferenced(int frameIndex, unsigned int currentTick) {
    if (std::find(queue_.begin(), queue_.end(), frameIndex) == queue_.end()) {
        queue_.push_back(frameIndex);
    }
}

void FIFOReplacer::onFrameFreed(int frameIndex) {
    auto it = std::find(queue_.begin(), queue_.end(), frameIndex);
    if (it != queue_.end()) queue_.erase(it);
}

// ─── LRU ─────────────────────────────────────────────────────────────────────
int LRUReplacer::selectVictim(FrameTable& ft, unsigned int currentTick) {
    int victim = -1;
    unsigned int minTick = UINT_MAX;
    const auto& frames = ft.getFrames();
    for (int i = 0; i < (int)frames.size(); ++i) {
        if (!frames[i].isFree && frames[i].segmentType != SegmentType::OS) {
            if (frames[i].lastAccessTick < minTick) {
                minTick = frames[i].lastAccessTick;
                victim = i;
            }
        }
    }
    return victim;
}

void LRUReplacer::onPageReferenced(int frameIndex, unsigned int currentTick) {}
void LRUReplacer::onFrameFreed(int frameIndex) {}

// ─── NRU ─────────────────────────────────────────────────────────────────────
int NRUReplacer::selectVictim(FrameTable& ft, unsigned int currentTick) {
    std::vector<int> classes[4];
    const auto& frames = ft.getFrames();
    for (int i = 0; i < (int)frames.size(); ++i) {
        if (!frames[i].isFree && frames[i].segmentType != SegmentType::OS) {
            int cls = (frames[i].referenced ? 2 : 0) + (frames[i].modified ? 1 : 0);
            classes[cls].push_back(i);
        }
    }
    for (int i = 0; i < 4; ++i) {
        if (!classes[i].empty()) {
            return classes[i].front(); // Can be random, taking front for simplicity
        }
    }
    return -1;
}

void NRUReplacer::onPageReferenced(int frameIndex, unsigned int currentTick) {}
void NRUReplacer::onFrameFreed(int frameIndex) {}

// ─── Second Chance ───────────────────────────────────────────────────────────
int SecondChanceReplacer::selectVictim(FrameTable& ft, unsigned int currentTick) {
    while (!queue_.empty()) {
        int candidate = queue_.front();
        queue_.erase(queue_.begin());
        Frame* f = ft.getFrame(candidate);
        if (f && f->referenced) {
            f->referenced = false; // Give second chance
            queue_.push_back(candidate);
        } else {
            return candidate;
        }
    }
    return -1;
}

void SecondChanceReplacer::onPageReferenced(int frameIndex, unsigned int currentTick) {
    if (std::find(queue_.begin(), queue_.end(), frameIndex) == queue_.end()) {
        queue_.push_back(frameIndex);
    }
}

void SecondChanceReplacer::onFrameFreed(int frameIndex) {
    auto it = std::find(queue_.begin(), queue_.end(), frameIndex);
    if (it != queue_.end()) queue_.erase(it);
}

// ─── Clock ───────────────────────────────────────────────────────────────────
ClockReplacer::ClockReplacer(int totalFrames) : totalFrames_(totalFrames) {}

int ClockReplacer::selectVictim(FrameTable& ft, unsigned int currentTick) {
    int startHand = clockHand_;
    while (true) {
        Frame* f = ft.getFrame(clockHand_);
        if (f && !f->isFree && f->segmentType != SegmentType::OS) {
            if (f->referenced) {
                f->referenced = false;
            } else {
                int victim = clockHand_;
                clockHand_ = (clockHand_ + 1) % totalFrames_;
                return victim;
            }
        }
        clockHand_ = (clockHand_ + 1) % totalFrames_;
        if (clockHand_ == startHand) {
            // Loop finished, all were referenced. On second pass, first one will be victim.
        }
    }
    return -1;
}

void ClockReplacer::onPageReferenced(int frameIndex, unsigned int currentTick) {}
void ClockReplacer::onFrameFreed(int frameIndex) {}

// ─── NFU (Not Frequently Used) ───────────────────────────────────────────────
int NFUReplacer::selectVictim(FrameTable& ft, unsigned int currentTick) {
    int victim = -1;
    unsigned int minCount = UINT_MAX;
    const auto& frames = ft.getFrames();
    for (int i = 0; i < (int)frames.size(); ++i) {
        if (!frames[i].isFree && frames[i].segmentType != SegmentType::OS) {
            if (frames[i].agingCounter < minCount) {
                minCount = frames[i].agingCounter;
                victim = i;
            }
        }
    }
    return victim;
}

void NFUReplacer::onPageReferenced(int frameIndex, unsigned int currentTick) {}
void NFUReplacer::onFrameFreed(int frameIndex) {}

// ─── Aging ───────────────────────────────────────────────────────────────────
int AgingReplacer::selectVictim(FrameTable& ft, unsigned int currentTick) {
    int victim = -1;
    unsigned int minCount = UINT_MAX;
    const auto& frames = ft.getFrames();
    for (int i = 0; i < (int)frames.size(); ++i) {
        if (!frames[i].isFree && frames[i].segmentType != SegmentType::OS) {
            if (frames[i].agingCounter < minCount) {
                minCount = frames[i].agingCounter;
                victim = i;
            }
        }
    }
    return victim;
}

void AgingReplacer::onPageReferenced(int frameIndex, unsigned int currentTick) {}
void AgingReplacer::onFrameFreed(int frameIndex) {}

// ─── Working Set ─────────────────────────────────────────────────────────────
WorkingSetReplacer::WorkingSetReplacer(unsigned int tau) : tau_(tau) {}

int WorkingSetReplacer::selectVictim(FrameTable& ft, unsigned int currentTick) {
    int victim = -1;
    unsigned int oldestTime = UINT_MAX;
    const auto& frames = ft.getFrames();
    
    for (int i = 0; i < (int)frames.size(); ++i) {
        if (!frames[i].isFree && frames[i].segmentType != SegmentType::OS) {
            unsigned int age = currentTick - frames[i].lastAccessTick;
            if (age > tau_) {
                // Not in working set
                return i;
            }
            if (frames[i].lastAccessTick < oldestTime) {
                oldestTime = frames[i].lastAccessTick;
                victim = i;
            }
        }
    }
    return victim; // Return oldest if all are in working set
}

void WorkingSetReplacer::onPageReferenced(int frameIndex, unsigned int currentTick) {}
void WorkingSetReplacer::onFrameFreed(int frameIndex) {}

// ─── WSClock ─────────────────────────────────────────────────────────────────
WSClockReplacer::WSClockReplacer(int totalFrames, unsigned int tau) : totalFrames_(totalFrames), tau_(tau) {}

int WSClockReplacer::selectVictim(FrameTable& ft, unsigned int currentTick) {
    int startHand = clockHand_;
    while (true) {
        Frame* f = ft.getFrame(clockHand_);
        if (f && !f->isFree && f->segmentType != SegmentType::OS) {
            if (f->referenced) {
                f->referenced = false;
            } else {
                unsigned int age = currentTick - f->lastAccessTick;
                if (age > tau_) {
                    int victim = clockHand_;
                    clockHand_ = (clockHand_ + 1) % totalFrames_;
                    return victim;
                }
            }
        }
        clockHand_ = (clockHand_ + 1) % totalFrames_;
        if (clockHand_ == startHand) {
            break;
        }
    }
    // Fallback if none outside WS, just take LRU equivalent
    int victim = -1;
    unsigned int oldestTime = UINT_MAX;
    const auto& frames = ft.getFrames();
    for (int i = 0; i < (int)frames.size(); ++i) {
         if (!frames[i].isFree && frames[i].segmentType != SegmentType::OS) {
              if (frames[i].lastAccessTick < oldestTime) {
                  oldestTime = frames[i].lastAccessTick;
                  victim = i;
              }
         }
    }
    return victim;
}

void WSClockReplacer::onPageReferenced(int frameIndex, unsigned int currentTick) {}
void WSClockReplacer::onFrameFreed(int frameIndex) {}
