package verifier

import (
	"bytes"
	"context"
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"

	"github.com/anip-protocol/anip/packages/go/generator"
	"github.com/anip-protocol/anip/packages/go/registryclient"
)

type VerifyOptions struct {
	DefinitionPath            string
	PackageBundle             string
	RegistryBase              string
	PackageID                 string
	PackageVersion            string
	PackageRef                string
	LockFile                  string
	ExpectedContractSignature string
	RequiredRegistryMode      string
	TrustedRegistryKeyID      string
}

type CheckResult struct {
	Name   string `json:"name"`
	Status string `json:"status"`
	Detail string `json:"detail,omitempty"`
}

type Result struct {
	Status                   string         `json:"status"`
	SourceKind               string         `json:"source_kind"`
	PackageID                string         `json:"package_id,omitempty"`
	PackageVersion           string         `json:"package_version,omitempty"`
	SchemaVersion            string         `json:"schema_version,omitempty"`
	DefinitionDigest         string         `json:"definition_digest"`
	RegistryDefinitionDigest string         `json:"registry_definition_digest,omitempty"`
	ManifestDigest           string         `json:"manifest_digest,omitempty"`
	LockDigest               string         `json:"lock_digest,omitempty"`
	ReceiptAuthority         string         `json:"receipt_authority,omitempty"`
	ReceiptKeyID             string         `json:"receipt_key_id,omitempty"`
	ReceiptAlgorithm         string         `json:"receipt_algorithm,omitempty"`
	ReceiptStatus            string         `json:"receipt_status,omitempty"`
	ContractSignature        string         `json:"contract_signature,omitempty"`
	Lineage                  map[string]any `json:"lineage,omitempty"`
	ProductRevision          any            `json:"product_revision,omitempty"`
	DeveloperRevision        any            `json:"developer_revision,omitempty"`
	RegistryReceiptSignature string         `json:"registry_receipt_signature,omitempty"`
	RegistrySigningMode      string         `json:"registry_signing_mode,omitempty"`
	RegistryActiveKeyID      string         `json:"registry_active_key_id,omitempty"`
	RegistryRecordPath       string         `json:"registry_record_path,omitempty"`
	AgentReadiness           map[string]any `json:"agent_consumption_readiness,omitempty"`
	AgentConsumability       map[string]any `json:"agent_consumability,omitempty"`
	Checks                   []CheckResult  `json:"checks"`
}

func VerifyServiceDefinition(ctx context.Context, client *http.Client, options VerifyOptions) (*Result, error) {
	loadedLock, err := generator.LoadPackageLock(options.LockFile)
	if err != nil {
		return nil, err
	}
	resolveOptions := generator.ResolveServiceDefinitionOptions{
		DefinitionPath:         options.DefinitionPath,
		PackageBundle:          options.PackageBundle,
		RegistryBase:           options.RegistryBase,
		PackageID:              options.PackageID,
		PackageVersion:         options.PackageVersion,
		PackageRef:             options.PackageRef,
		AllowUntrustedRegistry: true,
	}
	generator.ApplyPackageLockToResolveOptions(&resolveOptions, loadedLock)
	resolved, err := generator.ResolveServiceDefinition(ctx, client, resolveOptions)
	if err != nil {
		return nil, err
	}
	lockErr := generator.ValidateResolvedPackageLock(resolved, loadedLock)

	definitionDigest, err := computeCanonicalDigest(resolved.Definition)
	if err != nil {
		return nil, fmt.Errorf("compute definition digest: %w", err)
	}
	contractSignature := firstNonEmpty(resolved.ContractSignature, nestedString(resolved.Definition, "compiled_contract_identity", "signature"))

	result := &Result{
		SourceKind:               resolved.SourceKind,
		PackageID:                resolved.PackageID,
		PackageVersion:           resolved.PackageVersion,
		SchemaVersion:            resolved.SchemaVersion,
		DefinitionDigest:         definitionDigest,
		RegistryDefinitionDigest: resolved.DefinitionDigest,
		ManifestDigest:           resolved.ManifestDigest,
		LockDigest:               resolved.LockDigest,
		ReceiptAuthority:         resolved.ReceiptAuthority,
		ReceiptKeyID:             resolved.ReceiptKeyID,
		ReceiptAlgorithm:         resolved.ReceiptAlgorithm,
		ContractSignature:        contractSignature,
		Lineage:                  resolved.Lineage,
		RegistrySigningMode:      resolved.RegistrySigningMode,
		RegistryActiveKeyID:      resolved.RegistryActiveKeyID,
		RegistryRecordPath:       resolved.RegistryRecordPath,
		AgentReadiness:           resolved.AgentReadiness,
		AgentConsumability:       resolved.AgentConsumability,
	}

	result.addCheck("definition_digest_computed", definitionDigest != "", "definition digest was recomputed from canonical JSON")
	if loadedLock != nil {
		result.addCheck("package_lock_matches", lockErr == nil, lockCheckDetail(lockErr))
	}
	if definition, err := generator.ParseServiceDefinition(resolved.DefinitionBytes); err != nil {
		result.addCheck("service_definition_shape_valid", false, err.Error())
	} else if _, err := generator.BuildGenerationModel(definition); err != nil {
		result.addCheck("service_definition_shape_valid", false, err.Error())
	} else {
		result.addCheck("service_definition_shape_valid", true, "service definition is compatible with the current generation model")
		result.addIntegrationFrontingChecks(definition)
		result.addComputedAgentReadinessChecks(definition)
	}
	if resolved.DefinitionDigest != "" && resolved.SourceKind != "registry" {
		result.addCheck(
			"registry_definition_digest_matches",
			resolved.DefinitionDigest == definitionDigest,
			fmt.Sprintf("registry=%s computed=%s", resolved.DefinitionDigest, definitionDigest),
		)
	}
	result.addCheck("contract_signature_present", contractSignature != "", "compiled contract signature is present")
	if options.ExpectedContractSignature != "" {
		result.addCheck(
			"expected_contract_signature_matches",
			options.ExpectedContractSignature == contractSignature,
			fmt.Sprintf("expected=%s observed=%s", options.ExpectedContractSignature, contractSignature),
		)
	}

	if resolved.SourceKind == "package-bundle" {
		result.RegistryReceiptSignature = resolved.ReceiptSignature
		result.addCheck("bundle_receipt_present", resolved.ReceiptSignature != "", "package bundle receipt signature is present")
		if resolved.ManifestDigest != "" {
			manifestDigest, err := computeCanonicalDigest(resolved.Manifest)
			if err != nil {
				return nil, fmt.Errorf("compute manifest digest: %w", err)
			}
			result.addCheck(
				"bundle_manifest_digest_matches",
				resolved.ManifestDigest == manifestDigest,
				fmt.Sprintf("bundle=%s computed=%s", resolved.ManifestDigest, manifestDigest),
			)
		}
		if resolved.LockDigest != "" {
			lockDigest, err := computeCanonicalDigest(resolved.RecommendedLock)
			if err != nil {
				return nil, fmt.Errorf("compute lock digest: %w", err)
			}
			result.addCheck(
				"bundle_lock_digest_matches",
				resolved.LockDigest == lockDigest,
				fmt.Sprintf("bundle=%s computed=%s", resolved.LockDigest, lockDigest),
			)
		}
		if resolved.ReceiptSignature != "" {
			if strings.HasPrefix(resolved.ReceiptSignature, "ed25519:") {
				result.addBundleRegistryReceiptCheck(resolved, contractSignature, definitionDigest)
			} else {
				expectedReceiptSignature, err := computeReceiptSignature(resolved, contractSignature, definitionDigest)
				if err != nil {
					return nil, fmt.Errorf("compute package bundle receipt signature: %w", err)
				}
				result.addCheck(
					"bundle_receipt_signature_matches",
					resolved.ReceiptSignature == expectedReceiptSignature,
					fmt.Sprintf("bundle=%s computed=%s", resolved.ReceiptSignature, expectedReceiptSignature),
				)
			}
		}
	}

	if resolved.SourceKind == "registry" {
		result.RegistryReceiptSignature = resolved.ReceiptSignature
		for _, check := range resolved.RegistryTrustChecks {
			result.addCheck(check.Name, check.Status == "pass", check.Detail)
		}
		result.addRegistryTrustPolicyChecks(options)
	}
	if len(resolved.Lineage) > 0 {
		result.ProductRevision = resolved.Lineage["product_revision"]
		result.DeveloperRevision = resolved.Lineage["developer_revision"]
	}
	if resolved.SourceKind != "file" {
		result.addAgentReadinessChecks(resolved.AgentReadiness)
		result.addAgentConsumabilityChecks(resolved.AgentConsumability)
	}

	result.Status = "ok"
	for _, check := range result.Checks {
		if check.Status != "pass" {
			result.Status = "failed"
			break
		}
	}
	result.ReceiptStatus = receiptStatus(result)
	return result, nil
}

func lockCheckDetail(err error) string {
	if err != nil {
		return err.Error()
	}
	return "resolved package matches pinned lock file"
}

func (r *Result) addAgentConsumabilityChecks(consumability map[string]any) {
	r.addCheck(
		"agent_consumability_present",
		len(consumability) > 0,
		"agent consumability metadata is embedded in the package manifest or lock",
	)
	if len(consumability) == 0 {
		return
	}
	schemaVersion := strings.TrimSpace(stringValue(consumability["schema_version"]))
	r.addCheck(
		"agent_consumability_schema_present",
		schemaVersion != "",
		fmt.Sprintf("schema_version=%s", emptyLabel(schemaVersion)),
	)
	capabilities, _ := consumability["capabilities"].(map[string]any)
	r.addCheck(
		"agent_consumability_has_capability_hints",
		len(capabilities) > 0,
		fmt.Sprintf("capabilities=%d", len(capabilities)),
	)
}

func (r *Result) addComputedAgentReadinessChecks(definition *generator.AnipServiceDefinition) {
	if definition == nil {
		return
	}
	missingClassifications := []string{}
	for _, capability := range definition.CapabilityFormalizations {
		for _, input := range capability.Inputs {
			if !input.Required || verifierInputHasClassification(input) {
				continue
			}
			missingClassifications = append(missingClassifications, capability.CapabilityID+"."+input.InputName)
		}
	}
	r.addCheck(
		"agent_consumption_required_inputs_classified",
		len(missingClassifications) == 0,
		fmt.Sprintf("missing=%s", emptyLabel(strings.Join(missingClassifications, ","))),
	)
}

func verifierInputHasClassification(input generator.CapabilityInputFormalization) bool {
	return strings.TrimSpace(input.SemanticType) != "" ||
		strings.TrimSpace(input.InputFormat) != "" ||
		strings.TrimSpace(input.ValidationPattern) != "" ||
		strings.TrimSpace(input.ClarificationHint) != "" ||
		input.EntityReference ||
		len(input.AllowedValues) > 0
}

func (r *Result) addIntegrationFrontingChecks(definition *generator.AnipServiceDefinition) {
	if definition == nil || definition.IntegrationFronting == nil || len(definition.IntegrationFronting.CapabilityMappings) == 0 {
		r.addCheck("integration_fronting_not_declared", true, "service definition does not declare governed API/MCP fronting mappings")
		return
	}
	capabilityIDs := map[string]bool{}
	for _, capability := range definition.CapabilityFormalizations {
		capabilityIDs[capability.CapabilityID] = true
	}
	allMapped := true
	allBound := true
	mappingCount := 0
	rawOperationCount := 0
	for _, mapping := range definition.IntegrationFronting.CapabilityMappings {
		mappingCount++
		if !capabilityIDs[mapping.CapabilityID] {
			allMapped = false
		}
		bindings := mapping.BackendBindings
		if len(bindings) == 0 {
			bindings = []generator.IntegrationBackendBinding{{
				BackendKind:      mapping.BackendKind,
				ConnectionRef:    mapping.ConnectionRef,
				RawOperationRefs: mapping.RawOperationRefs,
			}}
		}
		for _, binding := range bindings {
			if strings.TrimSpace(binding.ConnectionRef) == "" || len(binding.RawOperationRefs) == 0 {
				allBound = false
				continue
			}
			rawOperationCount += len(binding.RawOperationRefs)
		}
	}
	r.addCheck(
		"integration_fronting_capabilities_formalized",
		allMapped,
		fmt.Sprintf("mappings=%d", mappingCount),
	)
	r.addCheck(
		"integration_fronting_raw_operations_governed",
		allBound && rawOperationCount > 0,
		fmt.Sprintf("raw_operations=%d; raw backend operations must be represented through governed capability mappings", rawOperationCount),
	)
}

func (r *Result) addAgentReadinessChecks(readiness map[string]any) {
	r.addCheck(
		"agent_consumption_readiness_present",
		len(readiness) > 0,
		"agent consumption readiness report is embedded in the package manifest or lock",
	)
	if len(readiness) == 0 {
		return
	}
	status := strings.TrimSpace(stringValue(readiness["status"]))
	r.addCheck(
		"agent_consumption_readiness_not_blocked",
		status != "" && status != "blocked",
		fmt.Sprintf("status=%s", emptyLabel(status)),
	)
	summary, _ := readiness["summary"].(map[string]any)
	blockers := numericValue(summary["blockers"])
	r.addCheck(
		"agent_consumption_readiness_has_no_blockers",
		blockers == 0,
		fmt.Sprintf("blockers=%g", blockers),
	)
	warnings := numericValue(summary["warnings"])
	r.addCheck(
		"agent_consumption_readiness_has_no_warnings",
		warnings == 0,
		fmt.Sprintf("warnings=%g", warnings),
	)
	probes := numericValue(summary["probes"])
	r.addCheck(
		"agent_consumption_readiness_has_simulator_probes",
		probes > 0,
		fmt.Sprintf("probes=%g", probes),
	)
}

func (r *Result) addRegistryTrustPolicyChecks(options VerifyOptions) {
	requiredMode := strings.ToLower(strings.TrimSpace(options.RequiredRegistryMode))
	if requiredMode != "" {
		observedMode := strings.ToLower(strings.TrimSpace(r.RegistrySigningMode))
		r.addCheck(
			"registry_trust_policy_signing_mode_present",
			observedMode != "",
			"registry signing mode metadata is required by verifier trust policy",
		)
		r.addCheck(
			"registry_trust_policy_signing_mode_matches",
			observedMode == requiredMode,
			fmt.Sprintf("required=%s observed=%s", requiredMode, emptyLabel(observedMode)),
		)
	}

	trustedKeyID := strings.TrimSpace(options.TrustedRegistryKeyID)
	if trustedKeyID != "" {
		receiptKeyID := strings.TrimSpace(r.ReceiptKeyID)
		r.addCheck(
			"registry_trust_policy_receipt_key_matches",
			receiptKeyID == trustedKeyID,
			fmt.Sprintf("trusted=%s receipt=%s", trustedKeyID, emptyLabel(receiptKeyID)),
		)
	}
}

func (r *Result) addBundleRegistryReceiptCheck(resolved *generator.ResolvedServiceDefinition, contractSignature string, definitionDigest string) {
	algorithm, keyID, signature, ok := parseRegistrySignature(resolved.ReceiptSignature)
	r.ReceiptAlgorithm = firstNonEmpty(r.ReceiptAlgorithm, algorithm)
	r.ReceiptKeyID = firstNonEmpty(r.ReceiptKeyID, keyID)
	r.addCheck("bundle_receipt_algorithm_supported", ok && algorithm == "ed25519", fmt.Sprintf("algorithm=%s", algorithm))

	publicKey, found := findBundlePublicKey(resolved.RegistryPublicKeys, keyID)
	r.addCheck("bundle_registry_public_key_present", found, fmt.Sprintf("key_id=%s", keyID))
	if !found || !ok {
		return
	}
	payload := map[string]any{
		"package_id":         resolved.PackageID,
		"package_version":    resolved.PackageVersion,
		"contract_signature": contractSignature,
		"definition_digest":  firstNonEmpty(resolved.DefinitionDigest, definitionDigest),
		"manifest_digest":    resolved.ManifestDigest,
		"lock_digest":        resolved.LockDigest,
		"issued_at":          resolved.ReceiptIssuedAt,
	}
	if resolved.PublisherID != "" {
		payload["publisher_id"] = resolved.PublisherID
	}
	if resolved.PublisherType != "" {
		payload["publisher_type"] = resolved.PublisherType
	}
	if len(resolved.Lineage) > 0 {
		payload["lineage"] = resolved.Lineage
	}
	bytes, err := json.Marshal(payload)
	r.addCheck(
		"bundle_receipt_signature_valid",
		err == nil && ed25519.Verify(publicKey, bytes, signature),
		"package bundle Registry receipt signature validates against bundled Ed25519 public key",
	)
}

func emptyLabel(value string) string {
	if strings.TrimSpace(value) == "" {
		return "not reported"
	}
	return value
}

func stringValue(value any) string {
	text, _ := value.(string)
	return text
}

func numericValue(value any) float64 {
	switch typed := value.(type) {
	case float64:
		return typed
	case float32:
		return float64(typed)
	case int:
		return float64(typed)
	case int64:
		return float64(typed)
	case json.Number:
		number, _ := typed.Float64()
		return number
	default:
		return 0
	}
}

func receiptStatus(result *Result) string {
	if result.RegistryReceiptSignature == "" {
		return "none"
	}
	if checkHasStatus(result.Checks, "registry_receipt_signature_valid", "pass") || checkHasStatus(result.Checks, "bundle_receipt_signature_matches", "pass") || checkHasStatus(result.Checks, "bundle_receipt_signature_valid", "pass") {
		return "verified"
	}
	if checkHasStatus(result.Checks, "registry_receipt_signature_valid", "fail") || checkHasStatus(result.Checks, "bundle_receipt_signature_matches", "fail") || checkHasStatus(result.Checks, "bundle_receipt_signature_valid", "fail") {
		return "failed"
	}
	return "present"
}

func checkHasStatus(checks []CheckResult, name string, status string) bool {
	for _, check := range checks {
		if check.Name == name && check.Status == status {
			return true
		}
	}
	return false
}

func computeReceiptSignature(resolved *generator.ResolvedServiceDefinition, contractSignature string, definitionDigest string) (string, error) {
	payload := map[string]any{
		"package_id":         resolved.PackageID,
		"package_version":    resolved.PackageVersion,
		"contract_signature": contractSignature,
		"definition_digest":  firstNonEmpty(resolved.DefinitionDigest, definitionDigest),
		"manifest_digest":    resolved.ManifestDigest,
		"issued_at":          resolved.ReceiptIssuedAt,
	}
	if resolved.ReceiptAuthority != "" {
		payload["authority"] = resolved.ReceiptAuthority
	}
	if len(resolved.Lineage) > 0 {
		payload["lineage"] = resolved.Lineage
	}
	return computeCanonicalDigest(payload)
}

func parseRegistrySignature(signature string) (string, string, []byte, bool) {
	parts := strings.Split(signature, ":")
	if len(parts) != 3 {
		return "", "", nil, false
	}
	raw, err := base64.StdEncoding.DecodeString(parts[2])
	if err != nil {
		return "", "", nil, false
	}
	return parts[0], parts[1], raw, true
}

func findBundlePublicKey(keys []registryclient.PublicKey, keyID string) (ed25519.PublicKey, bool) {
	for _, key := range keys {
		if key.KeyID != keyID || key.Algorithm != "ed25519" {
			continue
		}
		raw, err := base64.StdEncoding.DecodeString(key.PublicKey)
		if err != nil || len(raw) != ed25519.PublicKeySize {
			return nil, false
		}
		return ed25519.PublicKey(raw), true
	}
	return nil, false
}

func (r *Result) addCheck(name string, passed bool, detail string) {
	status := "fail"
	if passed {
		status = "pass"
	}
	r.Checks = append(r.Checks, CheckResult{Name: name, Status: status, Detail: detail})
}

func computeCanonicalDigest(payload any) (string, error) {
	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(payload); err != nil {
		return "", err
	}
	bytes := bytes.TrimSuffix(buffer.Bytes(), []byte("\n"))
	sum := sha256.Sum256(bytes)
	return "sha256:" + hex.EncodeToString(sum[:]), nil
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

func nestedString(payload map[string]any, keys ...string) string {
	var current any = payload
	for _, key := range keys {
		next, ok := current.(map[string]any)
		if !ok {
			return ""
		}
		current = next[key]
	}
	value, _ := current.(string)
	return value
}
