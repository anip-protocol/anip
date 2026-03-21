package server

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/crypto"
)

// AppendAudit assigns a sequence number, computes prev_hash, signs the entry, and appends it.
func AppendAudit(km *crypto.KeyManager, storage Storage, entry *core.AuditEntry) error {
	// Set timestamp if not already set.
	if entry.Timestamp == "" {
		entry.Timestamp = time.Now().UTC().Format(time.RFC3339)
	}

	// 1. Append entry (storage assigns sequence_number and previous_hash).
	appended, err := storage.AppendAuditEntry(entry)
	if err != nil {
		return fmt.Errorf("append audit entry: %w", err)
	}

	// Copy assigned fields back.
	*entry = *appended

	// 2. Sign the entry.
	entryMap := auditEntryToMap(entry)
	signature, err := km.SignAuditEntry(entryMap)
	if err != nil {
		return fmt.Errorf("sign audit entry: %w", err)
	}

	// 3. Update the signature in storage.
	if err := storage.UpdateAuditSignature(entry.SequenceNumber, signature); err != nil {
		return fmt.Errorf("update audit signature: %w", err)
	}

	entry.Signature = signature
	return nil
}

// QueryAudit queries audit entries scoped to a root principal.
func QueryAudit(storage Storage, rootPrincipal string, filters AuditFilters) (core.AuditResponse, error) {
	// Always scope to root_principal.
	filters.RootPrincipal = rootPrincipal

	entries, err := storage.QueryAuditEntries(filters)
	if err != nil {
		return core.AuditResponse{}, fmt.Errorf("query audit entries: %w", err)
	}

	return core.AuditResponse{Entries: entries}, nil
}

// auditEntryToMap converts an AuditEntry to a map[string]any for signing.
func auditEntryToMap(entry *core.AuditEntry) map[string]any {
	data, _ := json.Marshal(entry)
	var m map[string]any
	json.Unmarshal(data, &m)
	return m
}
