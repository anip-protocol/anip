package registryapi

type PublicationSummary struct {
	PackageID            string         `json:"package_id"`
	PackageVersion       string         `json:"package_version"`
	ProjectRef           string         `json:"project_ref"`
	ProductRevisionRef   string         `json:"product_revision_ref"`
	DeveloperRevisionRef string         `json:"developer_revision_ref"`
	ContractSignature    string         `json:"contract_signature"`
	PublisherID          string         `json:"publisher_id,omitempty"`
	PublisherType        string         `json:"publisher_type,omitempty"`
	Lineage              map[string]any `json:"lineage,omitempty"`
	PublishedAt          string         `json:"published_at"`
	DownloadCount        int64          `json:"download_count"`
}

type PackageSourceLink struct {
	Title string `json:"title"`
	URL   string `json:"url"`
}

type PackageImplementationMaterial struct {
	Title            string `json:"title,omitempty"`
	Ref              string `json:"ref"`
	BundleTreeSHA256 string `json:"bundle_tree_sha256,omitempty"`
}

type TemplateSummary struct {
	TemplateID      string         `json:"template_id"`
	TemplateVersion string         `json:"template_version"`
	TemplateKind    string         `json:"template_kind"`
	ProjectType     string         `json:"project_type"`
	ANIPSpecVersion string         `json:"anip_spec_version"`
	Domain          string         `json:"domain,omitempty"`
	Industry        string         `json:"industry,omitempty"`
	Systems         []string       `json:"systems,omitempty"`
	PublisherID     string         `json:"publisher_id,omitempty"`
	PublisherType   string         `json:"publisher_type,omitempty"`
	PublishedAt     string         `json:"published_at"`
	DownloadCount   int64          `json:"download_count"`
	Manifest        map[string]any `json:"manifest,omitempty"`
}

type PublishPackageRequest struct {
	PackageID               string                          `json:"package_id"`
	PackageVersion          string                          `json:"package_version"`
	ProjectRef              string                          `json:"project_ref"`
	ProductRevisionRef      string                          `json:"product_revision_ref"`
	DeveloperRevisionRef    string                          `json:"developer_revision_ref"`
	ContractSignature       string                          `json:"contract_signature"`
	PublisherID             string                          `json:"publisher_id,omitempty"`
	PublisherType           string                          `json:"publisher_type,omitempty"`
	Lineage                 map[string]any                  `json:"lineage,omitempty"`
	SchemaVersion           string                          `json:"schema_version"`
	Manifest                map[string]any                  `json:"manifest"`
	ServiceDefinition       map[string]any                  `json:"service_definition"`
	RecommendedLock         map[string]any                  `json:"recommended_lock"`
	Readme                  string                          `json:"readme,omitempty"`
	SourceLinks             []PackageSourceLink             `json:"source_links,omitempty"`
	ImplementationMaterials []PackageImplementationMaterial `json:"implementation_materials,omitempty"`
}

type RegistryPackageRecord struct {
	PackageID               string                          `json:"package_id"`
	PackageVersion          string                          `json:"package_version"`
	ProjectRef              string                          `json:"project_ref"`
	ProductRevisionRef      string                          `json:"product_revision_ref"`
	DeveloperRevisionRef    string                          `json:"developer_revision_ref"`
	ContractSignature       string                          `json:"contract_signature"`
	PublisherID             string                          `json:"publisher_id,omitempty"`
	PublisherType           string                          `json:"publisher_type,omitempty"`
	Lineage                 map[string]any                  `json:"lineage,omitempty"`
	SchemaVersion           string                          `json:"schema_version"`
	ManifestDigest          string                          `json:"manifest_digest"`
	DefinitionDigest        string                          `json:"definition_digest"`
	LockDigest              string                          `json:"lock_digest"`
	PublishedAt             string                          `json:"published_at"`
	DownloadCount           int64                           `json:"download_count"`
	Manifest                map[string]any                  `json:"manifest"`
	ServiceDefinition       map[string]any                  `json:"service_definition"`
	RecommendedLock         map[string]any                  `json:"recommended_lock"`
	Readme                  string                          `json:"readme,omitempty"`
	SourceLinks             []PackageSourceLink             `json:"source_links,omitempty"`
	ImplementationMaterials []PackageImplementationMaterial `json:"implementation_materials,omitempty"`
}

type RegistryReceipt struct {
	ReceiptID          string `json:"receipt_id"`
	PackageID          string `json:"package_id"`
	PackageVersion     string `json:"package_version"`
	RegistrySignature  string `json:"registry_signature"`
	SignatureAlgorithm string `json:"signature_algorithm,omitempty"`
	KeyID              string `json:"key_id,omitempty"`
	PublisherID        string `json:"publisher_id,omitempty"`
	PublisherType      string `json:"publisher_type,omitempty"`
	IssuedAt           string `json:"issued_at"`
}

type RegistryPackageLock struct {
	LockSchemaVersion   string `json:"lock_schema_version"`
	ArtifactType        string `json:"artifact_type"`
	SourceKind          string `json:"source_kind"`
	RegistryURL         string `json:"registry_url,omitempty"`
	PackageID           string `json:"package_id"`
	PackageVersion      string `json:"package_version"`
	ContractSignature   string `json:"contract_signature,omitempty"`
	SchemaVersion       string `json:"schema_version,omitempty"`
	DefinitionDigest    string `json:"definition_digest"`
	ManifestDigest      string `json:"manifest_digest,omitempty"`
	LockDigest          string `json:"lock_digest"`
	ReceiptSignature    string `json:"receipt_signature,omitempty"`
	ReceiptAuthority    string `json:"receipt_authority,omitempty"`
	ReceiptKeyID        string `json:"receipt_key_id,omitempty"`
	ReceiptAlgorithm    string `json:"receipt_algorithm,omitempty"`
	ReceiptIssuedAt     string `json:"receipt_issued_at,omitempty"`
	RegistrySigningMode string `json:"registry_signing_mode,omitempty"`
	RegistryActiveKeyID string `json:"registry_active_key_id,omitempty"`
	PublisherID         string `json:"publisher_id,omitempty"`
	PublisherType       string `json:"publisher_type,omitempty"`
}

type RegistryPublicKey struct {
	KeyID     string `json:"key_id"`
	Algorithm string `json:"algorithm"`
	PublicKey string `json:"public_key"`
}

type PublishPackageResult struct {
	Publication PublicationSummary    `json:"publication"`
	Package     RegistryPackageRecord `json:"package"`
	Receipt     RegistryReceipt       `json:"receipt"`
}

type PublishTemplateRequest struct {
	TemplateID      string         `json:"template_id"`
	TemplateVersion string         `json:"template_version"`
	PublisherID     string         `json:"publisher_id,omitempty"`
	PublisherType   string         `json:"publisher_type,omitempty"`
	Manifest        map[string]any `json:"manifest"`
	Template        map[string]any `json:"template"`
	Package         map[string]any `json:"package,omitempty"`
}

type RegistryTemplateRecord struct {
	TemplateID      string         `json:"template_id"`
	TemplateVersion string         `json:"template_version"`
	TemplateKind    string         `json:"template_kind"`
	ProjectType     string         `json:"project_type"`
	ANIPSpecVersion string         `json:"anip_spec_version"`
	Domain          string         `json:"domain,omitempty"`
	Industry        string         `json:"industry,omitempty"`
	Systems         []string       `json:"systems,omitempty"`
	PublisherID     string         `json:"publisher_id,omitempty"`
	PublisherType   string         `json:"publisher_type,omitempty"`
	PublishedAt     string         `json:"published_at"`
	DownloadCount   int64          `json:"download_count"`
	ManifestDigest  string         `json:"manifest_digest"`
	TemplateDigest  string         `json:"template_digest"`
	PackageDigest   string         `json:"package_digest"`
	Manifest        map[string]any `json:"manifest"`
	Template        map[string]any `json:"template"`
	Package         map[string]any `json:"package"`
}

type PublishTemplateResult struct {
	Template RegistryTemplateRecord `json:"template"`
}

type MigrationStatus struct {
	Applied       bool     `json:"applied"`
	AppliedCount  int      `json:"applied_count"`
	ExpectedCount int      `json:"expected_count"`
	Pending       []string `json:"pending,omitempty"`
}

type RegistryPublisher struct {
	PublisherID     string `json:"publisher_id"`
	PublisherType   string `json:"publisher_type"`
	DisplayName     string `json:"display_name"`
	Description     string `json:"description"`
	WebsiteURL      string `json:"website_url"`
	Status          string `json:"status"`
	TrustLevel      string `json:"trust_level"`
	CreatedByUserID string `json:"created_by_user_id,omitempty"`
	CreatedAt       string `json:"created_at"`
	UpdatedAt       string `json:"updated_at"`
}

type RegistryAuditEvent struct {
	EventID          string         `json:"event_id"`
	ActorUserID      string         `json:"actor_user_id,omitempty"`
	ActorPublisherID string         `json:"actor_publisher_id,omitempty"`
	TokenID          string         `json:"token_id,omitempty"`
	EventType        string         `json:"event_type"`
	TargetType       string         `json:"target_type"`
	TargetID         string         `json:"target_id"`
	Metadata         map[string]any `json:"metadata"`
	IPHash           string         `json:"ip_hash,omitempty"`
	UserAgentHash    string         `json:"user_agent_hash,omitempty"`
	CreatedAt        string         `json:"created_at"`
}

type PublishAuthContext struct {
	PublisherID   string `json:"publisher_id"`
	PublisherType string `json:"publisher_type"`
	TokenID       string `json:"token_id,omitempty"`
}
