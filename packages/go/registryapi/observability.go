package registryapi

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"sync"
	"time"
)

type ReadyStore interface {
	CheckReady(ctx context.Context) error
	MigrationStatus(ctx context.Context) (MigrationStatus, error)
}

type RegistryMetrics struct {
	mu                    sync.Mutex
	requestTotal          map[string]uint64
	requestDurationCount  map[string]uint64
	requestDurationSum    map[string]float64
	publishTotal          map[string]uint64
	downloadTotal         map[string]uint64
	readinessCheckTotal   map[string]uint64
	lastMigrationApplied  bool
	lastMigrationExpected int
	lastMigrationAppliedN int
}

func NewRegistryMetrics() *RegistryMetrics {
	return &RegistryMetrics{
		requestTotal:         map[string]uint64{},
		requestDurationCount: map[string]uint64{},
		requestDurationSum:   map[string]float64{},
		publishTotal:         map[string]uint64{},
		downloadTotal:        map[string]uint64{},
		readinessCheckTotal:  map[string]uint64{},
	}
}

func (m *RegistryMetrics) RecordRequest(method, route string, status int, duration time.Duration) {
	if m == nil {
		return
	}
	key := fmt.Sprintf(`method=%q,route=%q,status=%q`, method, route, fmt.Sprintf("%d", status))
	m.mu.Lock()
	defer m.mu.Unlock()
	m.requestTotal[key]++
	m.requestDurationCount[key]++
	m.requestDurationSum[key] += duration.Seconds()
}

func (m *RegistryMetrics) RecordPublish(kind, status string) {
	if m == nil {
		return
	}
	key := fmt.Sprintf(`kind=%q,status=%q`, kind, status)
	m.mu.Lock()
	defer m.mu.Unlock()
	m.publishTotal[key]++
}

func (m *RegistryMetrics) RecordDownload(kind string) {
	if m == nil {
		return
	}
	key := fmt.Sprintf(`kind=%q`, kind)
	m.mu.Lock()
	defer m.mu.Unlock()
	m.downloadTotal[key]++
}

func (m *RegistryMetrics) RecordReadiness(status string, migration MigrationStatus) {
	if m == nil {
		return
	}
	key := fmt.Sprintf(`status=%q`, status)
	m.mu.Lock()
	defer m.mu.Unlock()
	m.readinessCheckTotal[key]++
	m.lastMigrationApplied = migration.Applied
	m.lastMigrationExpected = migration.ExpectedCount
	m.lastMigrationAppliedN = migration.AppliedCount
}

func (m *RegistryMetrics) PrometheusText() string {
	if m == nil {
		m = NewRegistryMetrics()
	}
	m.mu.Lock()
	defer m.mu.Unlock()

	var builder strings.Builder
	builder.WriteString("# HELP anip_registry_http_requests_total Registry HTTP requests by method, route, and status.\n")
	builder.WriteString("# TYPE anip_registry_http_requests_total counter\n")
	writeCounterMap(&builder, "anip_registry_http_requests_total", m.requestTotal)

	builder.WriteString("# HELP anip_registry_http_request_duration_seconds_sum Total Registry HTTP request duration seconds.\n")
	builder.WriteString("# TYPE anip_registry_http_request_duration_seconds_sum counter\n")
	writeFloatMap(&builder, "anip_registry_http_request_duration_seconds_sum", m.requestDurationSum)

	builder.WriteString("# HELP anip_registry_http_request_duration_seconds_count Registry HTTP request duration sample count.\n")
	builder.WriteString("# TYPE anip_registry_http_request_duration_seconds_count counter\n")
	writeCounterMap(&builder, "anip_registry_http_request_duration_seconds_count", m.requestDurationCount)

	builder.WriteString("# HELP anip_registry_publish_total Package/template publish attempts by kind and status.\n")
	builder.WriteString("# TYPE anip_registry_publish_total counter\n")
	writeCounterMap(&builder, "anip_registry_publish_total", m.publishTotal)

	builder.WriteString("# HELP anip_registry_download_total Package/template download requests by kind.\n")
	builder.WriteString("# TYPE anip_registry_download_total counter\n")
	writeCounterMap(&builder, "anip_registry_download_total", m.downloadTotal)

	builder.WriteString("# HELP anip_registry_readiness_checks_total Readiness checks by status.\n")
	builder.WriteString("# TYPE anip_registry_readiness_checks_total counter\n")
	writeCounterMap(&builder, "anip_registry_readiness_checks_total", m.readinessCheckTotal)

	migrationApplied := 0
	if m.lastMigrationApplied {
		migrationApplied = 1
	}
	builder.WriteString("# HELP anip_registry_migrations_applied Whether all embedded migrations were applied on the last readiness check.\n")
	builder.WriteString("# TYPE anip_registry_migrations_applied gauge\n")
	builder.WriteString(fmt.Sprintf("anip_registry_migrations_applied %d\n", migrationApplied))
	builder.WriteString("# HELP anip_registry_migrations_expected Embedded migration count on the last readiness check.\n")
	builder.WriteString("# TYPE anip_registry_migrations_expected gauge\n")
	builder.WriteString(fmt.Sprintf("anip_registry_migrations_expected %d\n", m.lastMigrationExpected))
	builder.WriteString("# HELP anip_registry_migrations_applied_count Applied migration count on the last readiness check.\n")
	builder.WriteString("# TYPE anip_registry_migrations_applied_count gauge\n")
	builder.WriteString(fmt.Sprintf("anip_registry_migrations_applied_count %d\n", m.lastMigrationAppliedN))

	return builder.String()
}

func writeCounterMap(builder *strings.Builder, name string, values map[string]uint64) {
	keys := sortedMetricKeys(values)
	for _, key := range keys {
		builder.WriteString(fmt.Sprintf("%s{%s} %d\n", name, key, values[key]))
	}
}

func writeFloatMap(builder *strings.Builder, name string, values map[string]float64) {
	keys := sortedMetricKeys(values)
	for _, key := range keys {
		builder.WriteString(fmt.Sprintf("%s{%s} %.9f\n", name, key, values[key]))
	}
}

func sortedMetricKeys[V any](values map[string]V) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}
