package registryclient

import (
	"bytes"
	"context"
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
)

type PackageRecord struct {
	PackageID                 string                   `json:"package_id"`
	PackageVersion            string                   `json:"package_version"`
	ProjectRef                string                   `json:"project_ref"`
	ProductRevisionRef        string                   `json:"product_revision_ref"`
	DeveloperRevisionRef      string                   `json:"developer_revision_ref"`
	ContractSignature         string                   `json:"contract_signature"`
	PublisherID               string                   `json:"publisher_id,omitempty"`
	PublisherType             string                   `json:"publisher_type,omitempty"`
	Lineage                   map[string]any           `json:"lineage,omitempty"`
	SchemaVersion             string                   `json:"schema_version"`
	ManifestDigest            string                   `json:"manifest_digest"`
	DefinitionDigest          string                   `json:"definition_digest"`
	LockDigest                string                   `json:"lock_digest"`
	PackageExecutionSignature string                   `json:"package_execution_signature,omitempty"`
	PublishedAt               string                   `json:"published_at"`
	DownloadCount             int64                    `json:"download_count"`
	Manifest                  map[string]any           `json:"manifest"`
	ServiceDefinition         map[string]any           `json:"service_definition"`
	RecommendedLock           map[string]any           `json:"recommended_lock"`
	Readme                    string                   `json:"readme,omitempty"`
	SourceLinks               []SourceLink             `json:"source_links,omitempty"`
	ImplementationMaterials   []ImplementationMaterial `json:"implementation_materials,omitempty"`
	Lifecycle                 PackageLifecycle         `json:"lifecycle,omitempty"`
}

type PackageLifecycleReplacement struct {
	PackageID      string `json:"package_id,omitempty"`
	PackageVersion string `json:"package_version,omitempty"`
}

type PackageLifecycle struct {
	Status      string                       `json:"status,omitempty"`
	Reason      string                       `json:"reason,omitempty"`
	Replacement *PackageLifecycleReplacement `json:"replacement,omitempty"`
	UpdatedAt   string                       `json:"updated_at,omitempty"`
	UpdatedBy   string                       `json:"updated_by,omitempty"`
}

type ResolveOptions struct {
	AllowYankedPackage bool
}

type SourceLink struct {
	Title string `json:"title"`
	URL   string `json:"url"`
}

type ImplementationMaterial struct {
	Title            string `json:"title,omitempty"`
	Ref              string `json:"ref"`
	BundleTreeSHA256 string `json:"bundle_tree_sha256,omitempty"`
}

type Receipt struct {
	ReceiptID          string `json:"receipt_id"`
	PackageID          string `json:"package_id"`
	PackageVersion     string `json:"package_version"`
	RegistrySignature  string `json:"registry_signature"`
	SignatureAlgorithm string `json:"signature_algorithm"`
	KeyID              string `json:"key_id"`
	PublisherID        string `json:"publisher_id,omitempty"`
	PublisherType      string `json:"publisher_type,omitempty"`
	IssuedAt           string `json:"issued_at"`
}

type PublicKey struct {
	KeyID     string `json:"key_id"`
	Algorithm string `json:"algorithm"`
	PublicKey string `json:"public_key"`
}

type CheckResult struct {
	Name   string
	Status string
	Detail string
}

type ResolvedPackage struct {
	Package                   PackageRecord
	Receipt                   Receipt
	PublicKeys                []PublicKey
	SigningMode               string
	ActiveKeyID               string
	RegistryBaseURL           string
	PackageURL                string
	ReceiptURL                string
	KeysURL                   string
	DefinitionDigest          string
	ManifestDigest            string
	LockDigest                string
	PackageExecutionSignature string
	Checks                    []CheckResult
}

func ParsePackageRef(ref string) (string, string, error) {
	ref = strings.TrimSpace(ref)
	if ref == "" {
		return "", "", fmt.Errorf("package reference is required")
	}
	index := strings.LastIndex(ref, "@")
	if index <= 0 || index == len(ref)-1 {
		return "", "", fmt.Errorf("package reference must use package_id@package_version")
	}
	return strings.TrimSpace(ref[:index]), strings.TrimSpace(ref[index+1:]), nil
}

func ResolveAndVerify(ctx context.Context, client *http.Client, registryBase string, packageID string, packageVersion string) (*ResolvedPackage, error) {
	return ResolveAndVerifyWithOptions(ctx, client, registryBase, packageID, packageVersion, ResolveOptions{})
}

func ResolveAndVerifyWithOptions(ctx context.Context, client *http.Client, registryBase string, packageID string, packageVersion string, options ResolveOptions) (*ResolvedPackage, error) {
	if strings.TrimSpace(packageID) == "" || strings.TrimSpace(packageVersion) == "" {
		return nil, fmt.Errorf("package id and package version are required for registry resolution")
	}
	if client == nil {
		client = http.DefaultClient
	}

	apiBase := apiBaseURL(registryBase)
	if apiBase == "" {
		return nil, fmt.Errorf("registry base URL is required")
	}

	packageURL := fmt.Sprintf("%s/packages/%s/%s/download", apiBase, url.PathEscape(packageID), url.PathEscape(packageVersion))
	if options.AllowYankedPackage {
		packageURL += "?allow_yanked=true"
	}
	receiptURL := fmt.Sprintf("%s/packages/%s/%s/receipt", apiBase, url.PathEscape(packageID), url.PathEscape(packageVersion))
	keysURL := apiBase + "/keys"

	var record PackageRecord
	if err := fetchJSON(ctx, client, packageURL, "registry package", &record); err != nil {
		return nil, err
	}
	var receipt Receipt
	if err := fetchJSON(ctx, client, receiptURL, "registry receipt", &receipt); err != nil {
		return nil, err
	}
	var keyPayload struct {
		SigningMode string      `json:"signing_mode"`
		ActiveKeyID string      `json:"active_key_id"`
		Items       []PublicKey `json:"items"`
	}
	if err := fetchJSON(ctx, client, keysURL, "registry keys", &keyPayload); err != nil {
		return nil, err
	}

	resolved := &ResolvedPackage{
		Package:         record,
		Receipt:         receipt,
		PublicKeys:      keyPayload.Items,
		SigningMode:     keyPayload.SigningMode,
		ActiveKeyID:     keyPayload.ActiveKeyID,
		RegistryBaseURL: apiBase,
		PackageURL:      packageURL,
		ReceiptURL:      receiptURL,
		KeysURL:         keysURL,
	}
	resolved.verify()
	return resolved, nil
}

func (r *ResolvedPackage) Trusted() bool {
	for _, check := range r.Checks {
		if check.Status != "pass" {
			return false
		}
	}
	return true
}

func (r *ResolvedPackage) FailureSummary() string {
	failures := make([]string, 0)
	for _, check := range r.Checks {
		if check.Status == "fail" {
			failures = append(failures, check.Name)
		}
	}
	if len(failures) == 0 {
		return ""
	}
	return strings.Join(failures, ", ")
}

func apiBaseURL(registryBase string) string {
	base := strings.TrimRight(strings.TrimSpace(registryBase), "/")
	if base == "" {
		return ""
	}
	if strings.HasSuffix(base, "/registry-api/v1") {
		return base
	}
	return base + "/registry-api/v1"
}

func fetchJSON(ctx context.Context, client *http.Client, requestURL string, label string, target any) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, requestURL, nil)
	if err != nil {
		return fmt.Errorf("create %s request: %w", label, err)
	}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("fetch %s: %w", label, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("%s fetch failed (%d): %s", label, resp.StatusCode, strings.TrimSpace(string(body)))
	}
	if err := json.NewDecoder(resp.Body).Decode(target); err != nil {
		return fmt.Errorf("decode %s: %w", label, err)
	}
	return nil
}

func (r *ResolvedPackage) verify() {
	r.DefinitionDigest = canonicalDigest(r.Package.ServiceDefinition)
	r.ManifestDigest = canonicalDigest(r.Package.Manifest)
	r.LockDigest = canonicalDigest(r.Package.RecommendedLock)
	r.PackageExecutionSignature = firstNonEmpty(
		r.Package.PackageExecutionSignature,
		stringValue(r.Package.Manifest["package_execution_signature"]),
		stringValue(r.Package.RecommendedLock["package_execution_signature"]),
	)

	r.addCheck("registry_package_identity_matches", r.Package.PackageID == r.Receipt.PackageID && r.Package.PackageVersion == r.Receipt.PackageVersion, fmt.Sprintf("package=%s@%s receipt=%s@%s", r.Package.PackageID, r.Package.PackageVersion, r.Receipt.PackageID, r.Receipt.PackageVersion))
	if r.Package.PublisherID != "" || r.Receipt.PublisherID != "" {
		r.addCheck("registry_publisher_identity_matches", r.Package.PublisherID == r.Receipt.PublisherID && r.Package.PublisherType == r.Receipt.PublisherType, fmt.Sprintf("package=%s/%s receipt=%s/%s", r.Package.PublisherType, r.Package.PublisherID, r.Receipt.PublisherType, r.Receipt.PublisherID))
	}
	r.addCheck("registry_definition_digest_matches", r.Package.DefinitionDigest != "" && r.Package.DefinitionDigest == r.DefinitionDigest, fmt.Sprintf("registry=%s computed=%s", r.Package.DefinitionDigest, r.DefinitionDigest))
	r.addCheck("registry_manifest_digest_matches", r.Package.ManifestDigest != "" && r.Package.ManifestDigest == r.ManifestDigest, fmt.Sprintf("registry=%s computed=%s", r.Package.ManifestDigest, r.ManifestDigest))
	r.addCheck("registry_lock_digest_matches", r.Package.LockDigest != "" && r.Package.LockDigest == r.LockDigest, fmt.Sprintf("registry=%s computed=%s", r.Package.LockDigest, r.LockDigest))
	r.addCheck("registry_package_execution_signature_present", r.PackageExecutionSignature != "", fmt.Sprintf("signature=%s", r.PackageExecutionSignature))
	r.addCheck("registry_receipt_present", r.Receipt.RegistrySignature != "", "registry receipt signature is present")

	algorithm, keyID, signature, ok := parseRegistrySignature(r.Receipt.RegistrySignature)
	if r.Receipt.SignatureAlgorithm != "" {
		algorithm = r.Receipt.SignatureAlgorithm
	}
	if r.Receipt.KeyID != "" {
		keyID = r.Receipt.KeyID
	}
	r.addCheck("registry_receipt_algorithm_supported", ok && algorithm == "ed25519", fmt.Sprintf("algorithm=%s", algorithm))

	publicKey, found := findPublicKey(r.PublicKeys, keyID)
	r.addCheck("registry_public_key_present", found, fmt.Sprintf("key_id=%s", keyID))
	if found && ok {
		payload := map[string]any{
			"package_id":                  r.Package.PackageID,
			"package_version":             r.Package.PackageVersion,
			"contract_signature":          r.Package.ContractSignature,
			"definition_digest":           r.Package.DefinitionDigest,
			"manifest_digest":             r.Package.ManifestDigest,
			"lock_digest":                 r.Package.LockDigest,
			"package_execution_signature": r.PackageExecutionSignature,
			"issued_at":                   r.Receipt.IssuedAt,
		}
		if r.Package.PublisherID != "" {
			payload["publisher_id"] = r.Package.PublisherID
		}
		if r.Package.PublisherType != "" {
			payload["publisher_type"] = r.Package.PublisherType
		}
		if len(r.Package.Lineage) > 0 {
			payload["lineage"] = r.Package.Lineage
		}
		bytes, err := json.Marshal(payload)
		r.addCheck("registry_receipt_signature_valid", err == nil && ed25519.Verify(publicKey, bytes, signature), "registry receipt signature validates against advertised Ed25519 public key")
	}
}

func (r *ResolvedPackage) addCheck(name string, passed bool, detail string) {
	status := "fail"
	if passed {
		status = "pass"
	}
	r.Checks = append(r.Checks, CheckResult{Name: name, Status: status, Detail: detail})
}

func canonicalDigest(payload any) string {
	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(payload); err != nil {
		return ""
	}
	bytes := bytes.TrimSuffix(buffer.Bytes(), []byte("\n"))
	sum := sha256.Sum256(bytes)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

func stringValue(value any) string {
	text, _ := value.(string)
	return text
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

func findPublicKey(keys []PublicKey, keyID string) (ed25519.PublicKey, bool) {
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
