package enroll

import (
	"fmt"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/mem"

	"hyperfilelens/agent/internal/model"
)

type resourceCheckResult struct {
	CPUCount             int
	AvailableMemory      uint64
	RecommendedCPUs      int
	MinimumMemory        uint64
	RecommendedMemory    uint64
	MemoryHardFailure    bool
	MemoryRecommendation bool
	SwapConfigured       bool
}

func checkHostResources(role model.Role) resourceCheckResult {
	result := resourceCheckResult{RecommendedCPUs: 1}
	switch role {
	case model.RoleProxy:
		result.MinimumMemory = 512 * 1024 * 1024
		result.RecommendedMemory = 4 * 1024 * 1024 * 1024
		result.RecommendedCPUs = 2
	case model.RoleGateway:
		result.MinimumMemory = 1024 * 1024 * 1024
		result.RecommendedMemory = 4 * 1024 * 1024 * 1024
		result.RecommendedCPUs = 2
	default:
		result.MinimumMemory = 256 * 1024 * 1024
		result.RecommendedMemory = 1024 * 1024 * 1024
	}
	result.CPUCount, _ = cpu.Counts(true)
	if memory, err := mem.VirtualMemory(); err == nil {
		result.AvailableMemory = memory.Available
		result.MemoryHardFailure = memory.Available < result.MinimumMemory
		result.MemoryRecommendation = memory.Available < result.RecommendedMemory
	}
	if swap, err := mem.SwapMemory(); err == nil {
		result.SwapConfigured = swap.Total > 0
	}
	return result
}

func logHostResources(result resourceCheckResult, failures *preflightFailures) {
	if result.CPUCount < 1 {
		logWarn("CPU capacity could not be determined")
	} else if result.CPUCount < result.RecommendedCPUs {
		logWarnDetail(
			fmt.Sprintf("%d CPU core is available", result.CPUCount),
			fmt.Sprintf("%d or more CPU cores are recommended for concurrent workloads", result.RecommendedCPUs),
		)
	} else {
		logOKDetail("CPU capacity is sufficient", fmt.Sprintf("%d CPU cores available", result.CPUCount))
	}

	if result.AvailableMemory == 0 {
		logWarn("Available memory could not be determined")
		logSwapRecommendation(result)
		return
	}
	detail := fmt.Sprintf("%s available", humanBytes(result.AvailableMemory))
	if result.MemoryHardFailure {
		failures.add(
			"Available memory is below the safe installation minimum",
			detail+"; "+humanBytes(result.MinimumMemory)+" required",
			2,
		)
	}
	if result.MemoryRecommendation {
		logWarnDetail(
			"Available memory is below the recommended capacity",
			detail+"; "+humanBytes(result.RecommendedMemory)+" recommended",
		)
		logSwapRecommendation(result)
		return
	}
	logOKDetail("Memory capacity is sufficient", detail)
	logSwapRecommendation(result)
}

func logSwapRecommendation(result resourceCheckResult) {
	if !result.SwapConfigured {
		logWarnDetail(
			"No swap space is configured",
			"installation can continue, but memory pressure may terminate processes",
		)
	}
}
