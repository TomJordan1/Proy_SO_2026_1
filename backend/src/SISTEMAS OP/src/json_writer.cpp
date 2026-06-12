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
        entry["name"]         = p->name;
        entry["type"]         = processTypeLabel(p->type);
        entry["priority"]     = p->priority;
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
        entry["name"]       = p->name;
        entry["type"]       = processTypeLabel(p->type);
        entry["priority"]   = p->priority;
        entry["io_device"]  = p->ioDevice.has_value() ? json(p->ioDevice.value()) : json(nullptr);
        arr.push_back(entry);
    }
    return arr;
}

// ─── serializeProcessTable ───────────────────────────────────────────────────
json JsonWriter::serializeProcessTable(const std::vector<PCB*>& table) const {
    json arr = json::array();
    for (const PCB* p : table) {
        if (p->state == ProcessState::TERMINATED && p->isAlive() == false) {
            // Still include terminated processes in the table
        }
        json entry;
        entry["pid"]                = p->pid;
        entry["name"]               = p->name;
        entry["type"]               = processTypeLabel(p->type);
        entry["type_label"]         = processTypeLabel(p->type);
        entry["process_type"]       = processTypeToString(p->type);
        entry["state"]              = stateToString(p->state);
        entry["priority"]           = p->priority;
        entry["burst_time"]         = p->burstTime;
        entry["remaining_time"]     = p->remainingTime;
        entry["waiting_time"]       = p->waitingTime;
        entry["program_counter"]    = p->pc;
        entry["pc"]                 = p->pc;
        entry["pc_hex"]             = p->pcHex();
        entry["memory_size"]        = static_cast<double>(p->memorySizeMB);
        entry["mem_mb"]             = static_cast<double>(p->memorySizeMB);
        entry["completion_percent"] = p->completionPercent();
        entry["completion"]         = p->completionPercent();
        entry["cpu_id"]             = p->cpuId.has_value() ? json(p->cpuId.value()) : json(nullptr);
        entry["memory_base_address"]= p->memoryBaseAddress;
        entry["io_device"]          = p->ioDevice.has_value() ? json(p->ioDevice.value()) : json(nullptr);
        entry["arrival_tick"]       = p->arrivalTick;
        entry["response_time"]      = p->responseTime;
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
    m["avg_waiting"]      = snap.avgWaiting;
    m["avg_response"]     = snap.avgResponse;
    m["context_switches"] = snap.contextSwitches;
    m["starvation_events"]= snap.starvationEvents;
    m["error_rate"]       = snap.errorRate;
    return m;
}

// ─── serializeTimeline ───────────────────────────────────────────────────────
json JsonWriter::serializeTimeline(const TickSnapshot& snap) const {
    json arr = json::array();
    if (snap.hasCtxEvent) {
        json ev;
        ev["tick"]       = snap.ctxEvent.tick;
        ev["core_id"]    = snap.ctxEvent.coreId;
        ev["label"]      = snap.ctxEvent.label;
        ev["from_state"] = snap.ctxEvent.fromState;
        ev["to_state"]   = snap.ctxEvent.toState;
        arr.push_back(ev);
    }
    return arr;
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
    if (snap.memory) {
        tickObj["memory"] = serializeMemory(*snap.memory);
    }

    // IO devices
    if (snap.ioManager) {
        tickObj["io_devices"] = serializeIODevices(*snap.ioManager);
    }

    // Metrics
    tickObj["metrics"] = serializeMetrics(snap);

    // Timeline
    tickObj["timeline"] = serializeTimeline(snap);

    // Console logs
    json logs = json::array();
    for (const auto& line : snap.consoleLogs) {
        logs.push_back(line);
    }
    tickObj["console_logs"] = logs;

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
        root["ticks"]                       = output_["ticks"];

        std::ofstream out(filepath);
        if (!out.is_open()) return false;
        out << root.dump(2);
        return true;

    } catch (...) {
        return false;
    }
}
