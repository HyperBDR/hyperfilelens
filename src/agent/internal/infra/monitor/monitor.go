package monitor

import (
	"context"
	"os"
	"runtime"
	"strings"
	"time"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/disk"
	"github.com/shirou/gopsutil/v4/host"
	"github.com/shirou/gopsutil/v4/load"
	"github.com/shirou/gopsutil/v4/mem"
	"github.com/shirou/gopsutil/v4/net"
)

// Sample captures a point-in-time host resource snapshot aligned with control-plane monitor schema.
type Sample struct {
	Timestamp   time.Time      `json:"timestamp"`
	CPU         map[string]any `json:"cpu"`
	Memory      map[string]any `json:"memory"`
	Swap        map[string]any `json:"swap"`
	Disks       []any          `json:"disks"`
	DiskIO      []any          `json:"disk_io"`
	Networks    []any          `json:"networks"`
	LoadAverage []float64      `json:"load_average"`
	BootTime    float64        `json:"boot_time,omitempty"`
}

// Collector samples CPU, memory, disk, network, and load metrics.
type Collector struct{}

// NewCollector returns a resource monitor collector.
func NewCollector() *Collector {
	return &Collector{}
}

// SampleOnce returns the latest resource snapshot.
func (c *Collector) SampleOnce(ctx context.Context) (Sample, error) {
	_ = c
	_ = ctx
	now := time.Now().UTC()

	cpuPercent, _ := cpu.Percent(100*time.Millisecond, false)
	perCPU, _ := cpu.Percent(0, true)
	logical, _ := cpu.Counts(true)
	physical, _ := cpu.Counts(false)
	freq, _ := cpu.Info()

	cpuPayload := map[string]any{
		"usage_percent":   firstFloat(cpuPercent),
		"per_cpu_percent": perCPU,
		"logical_cores":   logical,
		"physical_cores":  physical,
	}
	if len(freq) > 0 {
		cpuPayload["frequency_mhz"] = freq[0].Mhz
	}

	vm, _ := mem.VirtualMemory()
	swap, _ := mem.SwapMemory()
	memoryPayload := map[string]any{
		"total":     vm.Total,
		"used":      vm.Used,
		"available": vm.Available,
		"percent":   vm.UsedPercent,
	}
	swapPayload := map[string]any{
		"total":   swap.Total,
		"used":    swap.Used,
		"free":    swap.Free,
		"percent": swap.UsedPercent,
	}

	disks := make([]any, 0)
	partitions, _ := disk.Partitions(false)
	for _, part := range partitions {
		mountpoint := normalizeMonitorMountpoint(part.Mountpoint)
		if mountpoint == "" {
			continue
		}
		row := map[string]any{
			"device":     part.Device,
			"mountpoint": mountpoint,
			"fstype":     part.Fstype,
		}
		if usage, err := disk.Usage(mountpoint); err == nil {
			row["total"] = usage.Total
			row["used"] = usage.Used
			row["free"] = usage.Free
			row["percent"] = usage.UsedPercent
		}
		disks = append(disks, row)
	}

	diskIO := make([]any, 0)
	if counters, err := disk.IOCounters(); err == nil {
		for name, item := range counters {
			diskIO = append(diskIO, map[string]any{
				"name":         name,
				"read_bytes":   item.ReadBytes,
				"write_bytes":  item.WriteBytes,
				"read_count":   item.ReadCount,
				"write_count":  item.WriteCount,
				"read_time":    item.ReadTime,
				"write_time":   item.WriteTime,
			})
		}
	}

	networks := make([]any, 0)
	if addrs, err := net.Interfaces(); err == nil {
		addrByName := map[string][]string{}
		for _, iface := range addrs {
			ips := make([]string, 0, len(iface.Addrs))
			for _, addr := range iface.Addrs {
				ips = append(ips, addr.Addr)
			}
			addrByName[iface.Name] = ips
		}
		if counters, err := net.IOCounters(true); err == nil {
			for _, item := range counters {
				networks = append(networks, map[string]any{
					"name":         item.Name,
					"bytes_sent":   item.BytesSent,
					"bytes_recv":   item.BytesRecv,
					"packets_sent": item.PacketsSent,
					"packets_recv": item.PacketsRecv,
					"errin":        item.Errin,
					"errout":       item.Errout,
					"dropin":       item.Dropin,
					"dropout":      item.Dropout,
					"addresses":    addrByName[item.Name],
				})
			}
		}
	}

	loadAvg := make([]float64, 0, 3)
	if runtime.GOOS != "windows" {
		if avg, err := load.Avg(); err == nil && avg != nil {
			loadAvg = []float64{avg.Load1, avg.Load5, avg.Load15}
		}
	} else if avg, err := load.Avg(); err == nil && avg != nil {
		loadAvg = []float64{avg.Load1, avg.Load5, avg.Load15}
	}

	var bootTime float64
	if info, err := host.Info(); err == nil {
		bootTime = float64(info.BootTime)
	}

	return Sample{
		Timestamp:   now,
		CPU:         cpuPayload,
		Memory:      memoryPayload,
		Swap:        swapPayload,
		Disks:       disks,
		DiskIO:      diskIO,
		Networks:    networks,
		LoadAverage: loadAvg,
		BootTime:    bootTime,
	}, nil
}

// ToPayload converts the sample to the heartbeat metrics payload.
func (s Sample) ToPayload() map[string]any {
	payload := map[string]any{
		"timestamp":    s.Timestamp.Format(time.RFC3339Nano),
		"cpu":          s.CPU,
		"memory":       s.Memory,
		"swap":         s.Swap,
		"disks":        s.Disks,
		"disk_io":      s.DiskIO,
		"networks":     s.Networks,
		"load_average": s.LoadAverage,
	}
	if s.BootTime > 0 {
		payload["boot_time"] = s.BootTime
	}
	payload["cpu_usage"] = nestedFloat(s.CPU, "usage_percent")
	payload["memory_usage"] = nestedFloat(s.Memory, "percent")
	payload["swap_usage"] = nestedFloat(s.Swap, "percent")
	payload["disk_usage"] = maxDiskPercent(s.Disks)
	payload["network_rx"] = sumNetworkField(s.Networks, "bytes_recv")
	payload["network_tx"] = sumNetworkField(s.Networks, "bytes_sent")
	if len(s.LoadAverage) > 0 {
		payload["load_1m"] = s.LoadAverage[0]
	}
	if len(s.LoadAverage) > 1 {
		payload["load_5m"] = s.LoadAverage[1]
	}
	if len(s.LoadAverage) > 2 {
		payload["load_15m"] = s.LoadAverage[2]
	}
	payload["metadata"] = map[string]any{"collector": "gopsutil", "goos": runtime.GOOS}
	return payload
}

func firstFloat(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	return values[0]
}

func nestedFloat(m map[string]any, key string) float64 {
	if m == nil {
		return 0
	}
	switch v := m[key].(type) {
	case float64:
		return v
	case float32:
		return float64(v)
	case int:
		return float64(v)
	case int64:
		return float64(v)
	default:
		return 0
	}
}

func maxDiskPercent(disks []any) float64 {
	max := 0.0
	for _, row := range disks {
		m, ok := row.(map[string]any)
		if !ok {
			continue
		}
		p := nestedFloat(m, "percent")
		if p > max {
			max = p
		}
	}
	return max
}

func sumNetworkField(networks []any, field string) float64 {
	total := 0.0
	for _, row := range networks {
		m, ok := row.(map[string]any)
		if !ok {
			continue
		}
		switch v := m[field].(type) {
		case float64:
			total += v
		case uint64:
			total += float64(v)
		case int64:
			total += float64(v)
		}
	}
	return total
}

func normalizeMonitorMountpoint(mountpoint string) string {
	clean := strings.TrimSpace(mountpoint)
	if runtime.GOOS == "windows" {
		if len(clean) == 2 && clean[1] == ':' {
			return strings.ToUpper(string(clean[0])) + `:\`
		}
		if len(clean) >= 3 && clean[1] == ':' && (clean[2] == '\\' || clean[2] == '/') {
			return strings.ToUpper(string(clean[0])) + `:\`
		}
	}
	return clean
}

// Hostname returns the local hostname for inventory frames.
func Hostname() string {
	h, err := os.Hostname()
	if err != nil {
		return ""
	}
	return h
}
