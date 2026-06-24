#include "json_writer.hpp"
#include <fstream>
#include <chrono>
#include <iomanip>
#include <sstream>
#include <ctime>

// ─── Constructor ─────────────────────────────────────────────────────────────
JsonWriter::JsonWriter(const std::string& simulationName,
                       const std::string& schedulerName,
                       int totalMemoryMB,
                       int numCpus)
    : simName_(simulationName), schedulerName_(schedulerName),
      totalMemoryMB_(totalMemoryMB), numCpus_(numCpus)
{
    output_["ticks"] = json::array();
}

// ─── serializeCore ───────────────────────────────────────────────────────────
json JsonWriter::serializeCore(const CoreSnapshot& core) const {
    json j;
    j["id"]                      = core.id;
    j["is_busy"]                 = core.isBusy;
    j["is_switching"]            = core.isSwitching;
    j["switch_overhead"]         = core.switchOverhead;
    j["switch_overhead_remaining"] = core.switchOverheadRemaining;
    j["scheduler"]               = core.schedulerName;
    j["busy_ticks"]              = core.busyTicks;

    if (core.process) {
        const PCB* p = core.process;
        json proc;
        proc["pid"]              = p->pid;
        proc["name"]             = p->name;
        proc["type"]             = processTypeLabel(p->type);
        proc["priority"]         = p->priority;
        proc["burst_time"]       = p->burstTime;
        proc["remaining"]        = p->remainingTime;
        proc["quantum_used"]     = p->quantumUsed;
        proc["quantum_rem"]      = 0;
        proc["quantum_remaining"]= 0;
        proc["pc"]               = p->pc;
        proc["pc_hex"]           = p->pcHex();
        proc["registers"]        = { {"AX", p->registers.AX},
                                     {"BX", p->registers.BX},
                                     {"CX", p->registers.CX},
                                     {"DX", p->registers.DX} };
        proc["completion"]       = p->completionPercent();
        proc["completion_percent"]= p->completionPercent();
        j["process"] = proc;
    } else {
        j["process"] = nullptr;
    }
    return j;
}

// ─── serializeReadyQueue ─────────────────────────────────────────────────────
json JsonWriter::serializeReadyQueue(const std::deque<PCB*>& q) const {
    json arr = json::array();
    for (const PCB* p : q) {
        json entry;
        entry["pid"]          = p->pid;
        entry["waiting_time"] = p->waitingTime;
        entry["waiting"]      = p->waitingTime;
        entry["remaining"]    = p->remainingTime;
        arr.push_back(entry);
    }
    return arr;
}

// ─── serializeWaiting ────────────────────────────────────────────────────────
json JsonWriter::serializeWaiting(const std::vector<PCB*>& waiting) const {
    json arr = json::array();
    for (const PCB* p : waiting) {
        json entry;
        entry["pid"]        = p->pid;
        entry["io_device"]  = p->ioDevice.has_value() ? json(p->ioDevice.value()) : json(nullptr);
        arr.push_back(entry);
    }
    return arr;
}

// ─── serializeProcessTable ───────────────────────────────────────────────────
json JsonWriter::serializeProcessTable(const std::vector<PCB*>& table) const {
    if (!globalInfoWritten_) {
        json staticArr = json::array();
        for (const PCB* p : table) {
            json s;
            s["pid"] = p->pid;
            s["name"] = p->name;
            s["type"] = processTypeLabel(p->type);
            s["type_label"] = processTypeLabel(p->type);
            s["process_type"] = processTypeToString(p->type);
            s["priority"] = p->priority;
            s["burst_time"] = p->burstTime;
            s["memory_size"] = static_cast<double>(p->memorySizeMB);
            s["mem_mb"] = static_cast<double>(p->memorySizeMB);
            s["arrival_tick"] = p->arrivalTick;
            s["memory_base_address"] = p->memoryBaseAddress;
            staticArr.push_back(s);
        }
        const_cast<json&>(output_)["global_process_info"] = staticArr;
        globalInfoWritten_ = true;
    }

    json arr = json::array();
    for (const PCB* p : table) {
        if (p->state == ProcessState::TERMINATED && p->isAlive() == false) {
            // Still include terminated processes in the table
        }
        json entry;
        entry["pid"]                = p->pid;
        entry["state"]              = stateToString(p->state);
        entry["remaining_time"]     = p->remainingTime;
        entry["waiting_time"]       = p->waitingTime;
        entry["program_counter"]    = p->pc;
        entry["pc"]                 = p->pc;
        entry["pc_hex"]             = p->pcHex();
        entry["completion_percent"] = p->completionPercent();
        entry["completion"]         = p->completionPercent();
        entry["cpu_id"]             = p->cpuId.has_value() ? json(p->cpuId.value()) : json(nullptr);
        entry["io_device"]          = p->ioDevice.has_value() ? json(p->ioDevice.value()) : json(nullptr);
        entry["response_time"]      = p->responseTime;
        entry["turnaround_time"]    = p->turnaround;
        if (p->errorCode != ErrorCode::NONE) {
            entry["error_code"] = errorCodeToString(p->errorCode);
        }
        arr.push_back(entry);
    }
    return arr;
}

// ─── serializeMemory ─────────────────────────────────────────────────────────
json JsonWriter::serializeMemory(const MemoryManager& mem) const {
    json j;

    // Stats
    auto s = mem.stats();
    j["stats"]["total_mb"]              = s.totalMB;
    j["stats"]["used_mb"]               = s.usedMB;
    j["stats"]["free_mb"]               = s.freeMB;
    j["stats"]["fragmentation_percent"] = s.fragmentationPercent;
    j["stats"]["strategy"]              = s.strategy;

    // Blocks
    json blocks = json::array();
    for (const auto& b : mem.blocks()) {
        json blk;
        blk["start_address"] = b.startAddress;
        blk["size"]          = b.size;
        blk["is_free"]       = b.isFree;
        blk["pid"]           = b.pid.has_value() ? json(b.pid.value()) : json(nullptr);
        blk["process_id"]    = b.pid.has_value() ? json(b.pid.value()) : json(nullptr);
        blk["segment_type"]  = segmentTypeToString(b.segmentType);
        blk["label"]         = b.label;
        blocks.push_back(blk);
    }
    j["blocks"] = blocks;

    // MMU table
    json mmu = json::array();
    for (const auto& e : mem.mmuTable()) {
        json entry;
        entry["pid"]           = e.pid;
        entry["logical_base"]  = e.logicalBase;
        entry["physical_base"] = e.physicalBase;
        entry["size"]          = e.size;
        mmu.push_back(entry);
    }
    j["mmu_table"] = mmu;

    return j;
}

// ─── serializePagedMemory ────────────────────────────────────────────────────
json JsonWriter::serializePagedMemory(const PagedMemoryManager& mem) const {
    json j;
    
    const auto& ft = mem.getFrameTable();
    j["total_frames"] = ft.getTotalFrames();
    j["os_reserved_frames"] = ft.getOsReservedFrames();

    // Process Frames (sparse) - ONLY write if changed!
    size_t currentHash = 0;
    for (const auto& f : ft.getFrames()) {
        if (!f.isFree && f.segmentType != SegmentType::OS) {
            currentHash ^= std::hash<int>()(f.index) + 0x9e3779b9 + (currentHash << 6) + (currentHash >> 2);
            currentHash ^= std::hash<int>()(f.pid.value_or(-1)) + 0x9e3779b9 + (currentHash << 6) + (currentHash >> 2);
            currentHash ^= std::hash<int>()(f.vpn) + 0x9e3779b9 + (currentHash << 6) + (currentHash >> 2);
        }
    }

    if (currentHash != lastProcessFramesHash_ || lastProcessFramesHash_ == 0) {
        json framesArr = json::array();
        for (const auto& f : ft.getFrames()) {
            if (!f.isFree && f.segmentType != SegmentType::OS) {
                json fObj;
                fObj["index"] = f.index;
                fObj["is_free"] = f.isFree;
                fObj["pid"] = f.pid.has_value() ? json(f.pid.value()) : json(nullptr);
                fObj["vpn"] = f.vpn;
                fObj["segment_type"] = segmentTypeToString(f.segmentType);
                framesArr.push_back(fObj);
            }
        }
        j["process_frames"] = framesArr;
        lastProcessFramesHash_ = currentHash;
    }
    // else: omit "process_frames" completely to save space
    // Swap Stats
    const auto& sm = mem.getSwapManager();
    j["swap"] = {
        {"max_pages", sm.getMaxPages()},
        {"used_pages", sm.getUsedPages()}
    };
    
    // TLB
    json tlbArr = json::array();
    // Non-const cast to get TLB for metrics output, or just use const if added
    auto tlb = const_cast<PagedMemoryManager&>(mem).getTLB();
    for (const auto& entry : tlb.getEntries()) {
        json tObj;
        tObj["pid"] = entry.pid;
        tObj["vpn"] = entry.vpn;
        tObj["frame_number"] = entry.frameNumber;
        tlbArr.push_back(tObj);
    }
    j["tlb"] = {
        {"hits", tlb.getHits()},
        {"misses", tlb.getMisses()},
        {"entries", tlbArr}
    };
    
    return j;
}

// ─── serializeIODevices ──────────────────────────────────────────────────────
json JsonWriter::serializeIODevices(const IOManager& io) const {
    json arr = json::array();
    for (const auto& dev : io.devices()) {
        json d;
        d["name"]            = dev.id;
        d["status"]          = dev.status();
        d["queue_length"]    = dev.queueLength();
        d["current_pid"]     = (dev.current.has_value()) ? json(dev.current->pid) : json(nullptr);
        d["current_name"]    = (dev.current.has_value()) ? json(dev.current->processName) : json(nullptr);
        d["progress_percent"]= dev.progressPercent();
        d["queue_pids"]      = dev.queuePids();
        arr.push_back(d);
    }
    return arr;
}

// ─── serializeMetrics ────────────────────────────────────────────────────────
json JsonWriter::serializeMetrics(const TickSnapshot& snap) const {
    json m;
    m["cpu_utilization"]  = snap.cpuUtilization;
    m["throughput"]       = snap.throughput;
    m["avg_turnaround"]   = snap.avgTurnaround;
    m["avg_waiting_time"] = snap.avgWaiting;
    m["avg_response_time"]= snap.avgResponse;
    m["context_switches"] = snap.contextSwitches;
    m["starvation_events"]= snap.starvationEvents;
    m["total_errors"]     = snap.totalErrors;
    m["total_completed"]  = snap.totalCompleted;
    return m;
}



// ─── recordTick ──────────────────────────────────────────────────────────────
void JsonWriter::recordTick(const TickSnapshot& snap) {
    json tickObj;
    tickObj["tick"] = snap.tick;

    // Cores
    json coresArr = json::array();
    for (const auto& c : snap.cores) {
        coresArr.push_back(serializeCore(c));
    }
    tickObj["cores"] = coresArr;

    // Ready queues (array of arrays)
    json rqArr = json::array();
    for (const auto& q : snap.readyQueues) {
        rqArr.push_back(serializeReadyQueue(q));
    }
    tickObj["ready_queues"] = rqArr;

    // Waiting list
    tickObj["waiting"] = serializeWaiting(snap.waitingList);

    // Process table
    tickObj["process_table"] = serializeProcessTable(snap.processTable);

    // Memory
    if (snap.pagedMemory) {
        tickObj["memory"] = serializePagedMemory(*snap.pagedMemory);
        tickObj["memory"]["type"] = "PAGED";
    } else if (snap.memory) {
        tickObj["memory"] = serializeMemory(*snap.memory);
        tickObj["memory"]["type"] = "CONTIGUOUS";
    }

    // IO devices
    if (snap.ioManager) {
        tickObj["io_devices"] = serializeIODevices(*snap.ioManager);
    }

    // Metrics
    tickObj["metrics"] = serializeMetrics(snap);

    // Console logs from this tick
    json logsArr = json::array();
    for (const auto& msg : snap.consoleLogs) {
        logsArr.push_back(msg);
    }
    tickObj["console_logs"] = logsArr;

    output_["ticks"].push_back(tickObj);
}

// ─── write ───────────────────────────────────────────────────────────────────
bool JsonWriter::write(const std::string& filepath) const {
    try {
        // Build metadata
        // Get current timestamp
        auto now = std::chrono::system_clock::now();
        std::time_t t = std::chrono::system_clock::to_time_t(now);
        std::ostringstream oss;
        struct tm tm_info;
#ifdef _WIN32
        localtime_s(&tm_info, &t);
#else
        localtime_r(&t, &tm_info);
#endif
        oss << std::put_time(&tm_info, "%Y-%m-%dT%H:%M:%S");

        json root;
        root["metadata"]["version"]         = "1.0";
        root["metadata"]["simulation_name"] = simName_;
        root["metadata"]["generated_at"]    = oss.str();
        root["metadata"]["total_ticks"]     = (int)output_["ticks"].size();
        root["metadata"]["scheduler"]       = schedulerName_;
        root["metadata"]["total_memory_mb"] = totalMemoryMB_;
        root["metadata"]["num_cpus"]        = numCpus_;
        root["global_process_info"]         = output_["global_process_info"];
        root["ticks"]                       = output_["ticks"];

        std::ofstream out(filepath);
        if (!out.is_open()) return false;
        out << root.dump(1);
        return true;

    } catch (...) {
        return false;
    }
}
