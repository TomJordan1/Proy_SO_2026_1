#pragma once
#include "types.hpp"
#include "pcb.hpp"
#include <string>
#include <vector>

// ─── JSON Reader ─────────────────────────────────────────────────────────────
// Parses the simulation input JSON (escenario_modelo.json) into a SimConfig
// and a list of ProcessDef objects.
class JsonReader {
public:
    // Load and parse the input JSON file.
    // Returns true if successful; false on error (see errorMessage()).
    bool load(const std::string& filepath);

    const SimConfig&              config()   const { return config_; }
    const std::vector<ProcessDef>& processes() const { return processes_; }
    const std::string&            errorMessage() const { return error_; }

private:
    SimConfig              config_;
    std::vector<ProcessDef> processes_;
    std::string            error_;
};
