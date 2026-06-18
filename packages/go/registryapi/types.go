package registryapi

type GitHubOAuthIdentity struct {
	GitHubUserID string `json:"github_user_id"`
	Login        string `json:"login"`
	DisplayName  string `json:"display_name"`
	Email        string `json:"email,omitempty"`
	AvatarURL    string `json:"avatar_url,omitempty"`
	ProfileURL   string `json:"profile_url,omitempty"`
}

type RegistryUser struct {
	UserID       string `json:"user_id"`
	GitHubUserID string `json:"github_user_id,omitempty"`
	GitHubLogin  string `json:"github_login,omitempty"`
	DisplayName  string `json:"display_name"`
	Email        string `json:"email,omitempty"`
	Status       string `json:"status"`
	CreatedAt    string `json:"created_at"`
	UpdatedAt    string `json:"updated_at"`
	LastLoginAt  string `json:"last_login_at,omitempty"`
}

type RegistryBrowserSessionContext struct {
	User      RegistryUser               `json:"user"`
	Publisher *RegistryPublisher         `json:"publisher,omitempty"`
	Scopes    RegistryPublishTokenScopes `json:"scopes"`
	Admin     bool                       `json:"admin,omitempty"`
}

type PublicationSummary struct {
	PackageID            string            `json:"package_id"`
	PackageVersion       string            `json:"package_version"`
	ProjectRef           string            `json:"project_ref"`
	ProductRevisionRef   string            `json:"product_revision_ref"`
	DeveloperRevisionRef string            `json:"developer_revision_ref"`
	ContractSignature    string            `json:"contract_signature"`
	PublisherID          string            `json:"publisher_id,omitempty"`
	PublisherType        string            `json:"publisher_type,omitempty"`
	Publisher            *PublisherSummary `json:"publisher,omitempty"`
	Lineage              map[string]any    `json:"lineage,omitempty"`
	PublishedAt          string            `json:"published_at"`
	DownloadCount        int64             `json:"download_count"`
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
	TemplateID      string            `json:"template_id"`
	TemplateVersion string            `json:"template_version"`
	TemplateKind    string            `json:"template_kind"`
	ProjectType     string            `json:"project_type"`
	ANIPSpecVersion string            `json:"anip_spec_version"`
	Domain          string            `json:"domain,omitempty"`
	Industry        string            `json:"industry,omitempty"`
	Systems         []string          `json:"systems,omitempty"`
	PublisherID     string            `json:"publisher_id,omitempty"`
	PublisherType   string            `json:"publisher_type,omitempty"`
	Publisher       *PublisherSummary `json:"publisher,omitempty"`
	PublishedAt     string            `json:"published_at"`
	DownloadCount   int64             `json:"download_count"`
	Manifest        map[string]any    `json:"manifest,omitempty"`
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
	Publisher               *PublisherSummary               `json:"publisher,omitempty"`
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
	TemplateID      string            `json:"template_id"`
	TemplateVersion string            `json:"template_version"`
	TemplateKind    string            `json:"template_kind"`
	ProjectType     string            `json:"project_type"`
	ANIPSpecVersion string            `json:"anip_spec_version"`
	Domain          string            `json:"domain,omitempty"`
	Industry        string            `json:"industry,omitempty"`
	Systems         []string          `json:"systems,omitempty"`
	PublisherID     string            `json:"publisher_id,omitempty"`
	PublisherType   string            `json:"publisher_type,omitempty"`
	Publisher       *PublisherSummary `json:"publisher,omitempty"`
	PublishedAt     string            `json:"published_at"`
	DownloadCount   int64             `json:"download_count"`
	ManifestDigest  string            `json:"manifest_digest"`
	TemplateDigest  string            `json:"template_digest"`
	PackageDigest   string            `json:"package_digest"`
	Manifest        map[string]any    `json:"manifest"`
	Template        map[string]any    `json:"template"`
	Package         map[string]any    `json:"package"`
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

type PublisherSelfServiceContext struct {
	Publisher RegistryPublisher          `json:"publisher"`
	Scopes    RegistryPublishTokenScopes `json:"scopes"`
}

type PublisherSummary struct {
	PublisherID   string `json:"publisher_id"`
	PublisherType string `json:"publisher_type"`
	DisplayName   string `json:"display_name"`
	WebsiteURL    string `json:"website_url,omitempty"`
	Status        string `json:"status"`
	TrustLevel    string `json:"trust_level"`
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

type RegistryPublishTokenScopes struct {
	Operations  []string `json:"operations"`
	Namespaces  []string `json:"namespaces"`
	PackageIDs  []string `json:"package_ids,omitempty"`
	TemplateIDs []string `json:"template_ids,omitempty"`
}

type RegistryPublishTokenSummary struct {
	TokenID     string                     `json:"token_id"`
	PublisherID string                     `json:"publisher_id"`
	TokenHash   string                     `json:"-"`
	Label       string                     `json:"label"`
	Scopes      RegistryPublishTokenScopes `json:"scopes"`
	ExpiresAt   string                     `json:"expires_at,omitempty"`
	LastUsedAt  string                     `json:"last_used_at,omitempty"`
	RevokedAt   string                     `json:"revoked_at,omitempty"`
	CreatedAt   string                     `json:"created_at"`
	UpdatedAt   string                     `json:"updated_at"`
}

type CreatePublishTokenRequest struct {
	Label     string                     `json:"label"`
	Scopes    RegistryPublishTokenScopes `json:"scopes"`
	ExpiresAt string                     `json:"expires_at,omitempty"`
}

type CreatePublishTokenResult struct {
	Token       RegistryPublishTokenSummary `json:"token"`
	BearerToken string                      `json:"bearer_token"`
}

type PublisherArtifactSummary struct {
	ArtifactKind string `json:"artifact_kind"`
	ArtifactID   string `json:"artifact_id"`
	Namespace    string `json:"namespace"`
	Status       string `json:"status"`
	CreatedAt    string `json:"created_at"`
	UpdatedAt    string `json:"updated_at"`
}

type UpdatePublisherRequest struct {
	DisplayName string `json:"display_name"`
	Description string `json:"description"`
	WebsiteURL  string `json:"website_url"`
}

type RegistryNamespaceSummary struct {
	Namespace     string   `json:"namespace"`
	PublisherID   string   `json:"publisher_id"`
	ArtifactKinds []string `json:"artifact_kinds"`
	Status        string   `json:"status"`
	CreatedAt     string   `json:"created_at"`
	UpdatedAt     string   `json:"updated_at"`
}

type PaginatedRegistryUsers struct {
	Items  []RegistryUser `json:"items"`
	Total  int            `json:"total"`
	Limit  int            `json:"limit"`
	Offset int            `json:"offset"`
}

type PaginatedRegistryPublishers struct {
	Items  []RegistryPublisher `json:"items"`
	Total  int                 `json:"total"`
	Limit  int                 `json:"limit"`
	Offset int                 `json:"offset"`
}

type PaginatedRegistryNamespaces struct {
	Items  []RegistryNamespaceSummary `json:"items"`
	Total  int                        `json:"total"`
	Limit  int                        `json:"limit"`
	Offset int                        `json:"offset"`
}

type PaginatedPublisherArtifacts struct {
	Items  []PublisherArtifactSummary `json:"items"`
	Total  int                        `json:"total"`
	Limit  int                        `json:"limit"`
	Offset int                        `json:"offset"`
}

type RegistryAdminListQuery struct {
	Search string
	Status string
	Limit  int
	Offset int
}

type CreateNamespaceRequest struct {
	Namespace     string   `json:"namespace"`
	ArtifactKinds []string `json:"artifact_kinds"`
}

type UpdateNamespaceStatusRequest struct {
	Status string `json:"status"`
	Reason string `json:"reason,omitempty"`
}

type UpdatePublisherStatusRequest struct {
	Status     string `json:"status"`
	TrustLevel string `json:"trust_level,omitempty"`
	Reason     string `json:"reason,omitempty"`
}

type UpdateArtifactOwnershipStatusRequest struct {
	Status string `json:"status"`
	Reason string `json:"reason,omitempty"`
}

type TransferArtifactOwnershipRequest struct {
	TargetPublisherID string `json:"target_publisher_id"`
	TargetNamespace   string `json:"target_namespace"`
	Reason            string `json:"reason,omitempty"`
}

type TransferNamespaceRequest struct {
	TargetPublisherID string `json:"target_publisher_id"`
	Reason            string `json:"reason,omitempty"`
}

type RegistryAbuseReport struct {
	ReportID        string `json:"report_id"`
	TargetKind      string `json:"target_kind"`
	TargetID        string `json:"target_id"`
	Category        string `json:"category"`
	Reason          string `json:"reason"`
	ReporterContact string `json:"reporter_contact,omitempty"`
	Status          string `json:"status"`
	Resolution      string `json:"resolution,omitempty"`
	CreatedAt       string `json:"created_at"`
	UpdatedAt       string `json:"updated_at"`
}

type PaginatedRegistryAbuseReports struct {
	Items  []RegistryAbuseReport `json:"items"`
	Total  int                   `json:"total"`
	Limit  int                   `json:"limit"`
	Offset int                   `json:"offset"`
}

type CreateAbuseReportRequest struct {
	TargetKind      string `json:"target_kind"`
	TargetID        string `json:"target_id"`
	Category        string `json:"category"`
	Reason          string `json:"reason"`
	ReporterContact string `json:"reporter_contact,omitempty"`
}

type UpdateAbuseReportStatusRequest struct {
	Status     string `json:"status"`
	Resolution string `json:"resolution,omitempty"`
}

type ApplyAbuseTakedownRequest struct {
	Reason string `json:"reason,omitempty"`
}
