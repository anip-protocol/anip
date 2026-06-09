package generator

type DependencySource string

const (
	DependencySourceRegistry DependencySource = "registry"
	DependencySourceLocal    DependencySource = "local"
)

type HttpRuntime string

const (
	HttpRuntimeHono    HttpRuntime = "hono"
	HttpRuntimeExpress HttpRuntime = "express"
	HttpRuntimeFastify HttpRuntime = "fastify"
)

type JavaFramework string

const (
	JavaFrameworkSpringBoot JavaFramework = "spring-boot"
	JavaFrameworkQuarkus    JavaFramework = "quarkus"
)

type Transport string

const (
	TransportHTTP  Transport = "http"
	TransportStdio Transport = "stdio"
)

type AnipServiceDefinition struct {
	ArtifactType             string                     `json:"artifact_type,omitempty"`
	ContractSchemaVersion    string                     `json:"contract_schema_version,omitempty"`
	CompiledContractIdentity *CompiledContractIdentity  `json:"compiled_contract_identity,omitempty"`
	Identity                 *ServiceIdentity           `json:"identity,omitempty"`
	Authority                *AuthorityConfig           `json:"authority,omitempty"`
	Audit                    *AuditConfig               `json:"audit,omitempty"`
	Generation               *GenerationConfig          `json:"generation,omitempty"`
	ServiceTopologyBindings  []ServiceTopologyBinding   `json:"service_topology_bindings,omitempty"`
	CapabilityFormalizations []CapabilityFormalization  `json:"capability_formalizations,omitempty"`
	PermissionIntentBindings []PermissionIntentBinding  `json:"permission_intent_bindings,omitempty"`
	RuntimePolicyBindings    []RuntimePolicyBinding     `json:"runtime_policy_bindings,omitempty"`
	IntegrationFronting      *IntegrationFrontingConfig `json:"integration_fronting,omitempty"`
}

type CompiledContractIdentity struct {
	Signature          string `json:"signature,omitempty"`
	SignatureAlgorithm string `json:"signature_algorithm,omitempty"`
}

type ServiceIdentity struct {
	SystemName        string `json:"system_name,omitempty"`
	DomainName        string `json:"domain_name,omitempty"`
	DeliveryModel     string `json:"delivery_model,omitempty"`
	ArchitectureShape string `json:"architecture_shape,omitempty"`
}

type AuthorityConfig struct {
	ApprovalExpectation   string `json:"approval_expectation,omitempty"`
	BlockedFailurePosture string `json:"blocked_failure_posture,omitempty"`
}

type AuditConfig struct {
	DurableRecordsRequired    bool `json:"durable_records_required,omitempty"`
	SearchableHistoryRequired bool `json:"searchable_history_required,omitempty"`
}

type GenerationConfig struct {
	Protocols          []string `json:"protocols,omitempty"`
	LayoutStrategy     string   `json:"layout_strategy,omitempty"`
	SelectedServiceIDs []string `json:"selected_service_ids,omitempty"`
}

type ServiceTopologyBinding struct {
	ID                      string   `json:"id,omitempty"`
	ServiceID               string   `json:"service_id"`
	ServiceName             string   `json:"service_name,omitempty"`
	SourceRole              string   `json:"source_role,omitempty"`
	SourceCapabilities      []string `json:"source_capabilities,omitempty"`
	FormalizedCapabilityIDs []string `json:"formalized_capability_ids,omitempty"`
	OwnedConceptIDs         []string `json:"owned_concept_ids,omitempty"`
}

type CapabilityFormalization struct {
	ID                string                         `json:"id,omitempty"`
	Kind              string                         `json:"kind,omitempty"`
	Composition       *Composition                   `json:"composition,omitempty"`
	GrantPolicy       *GrantPolicy                   `json:"grant_policy,omitempty"`
	SourceKind        string                         `json:"source_kind,omitempty"`
	ServiceID         string                         `json:"service_id"`
	CapabilityID      string                         `json:"capability_id"`
	Title             string                         `json:"title"`
	Summary           string                         `json:"summary"`
	EntityTargeted    bool                           `json:"entity_targeted,omitempty"`
	SubjectKind       string                         `json:"subject_kind,omitempty"`
	ContextType       string                         `json:"context_type,omitempty"`
	OutputIntent      string                         `json:"output_intent,omitempty"`
	IntentType        string                         `json:"intent_type"`
	OperationType     string                         `json:"operation_type"`
	SideEffectLevel   string                         `json:"side_effect_level"`
	ImplementationFit *ImplementationFit             `json:"implementation_fit,omitempty"`
	BusinessEffects   *BusinessEffects               `json:"business_effects,omitempty"`
	MinimumScope      []string                       `json:"minimum_scope,omitempty"`
	BackendOperation  string                         `json:"backend_operation"`
	PathTemplate      string                         `json:"path_template"`
	OutputShape       string                         `json:"output_shape"`
	Inputs            []CapabilityInputFormalization `json:"inputs"`
}

type ImplementationFit struct {
	Category  string `json:"category,omitempty"`
	Rationale string `json:"rationale,omitempty"`
}

type BusinessEffects struct {
	Produces       []string `json:"produces,omitempty"`
	DoesNotProduce []string `json:"does_not_produce,omitempty"`
}

type CompositionStep struct {
	ID                string `json:"id"`
	Capability        string `json:"capability"`
	EmptyResultSource bool   `json:"empty_result_source,omitempty"`
	EmptyResultPath   string `json:"empty_result_path,omitempty"`
}

type FailurePolicy struct {
	ChildClarification    string `json:"child_clarification"`
	ChildDenial           string `json:"child_denial"`
	ChildApprovalRequired string `json:"child_approval_required"`
	ChildError            string `json:"child_error"`
}

type AuditPolicy struct {
	RecordChildInvocations bool `json:"record_child_invocations"`
	ParentTaskLineage      bool `json:"parent_task_lineage"`
}

type Composition struct {
	AuthorityBoundary string                       `json:"authority_boundary"`
	Steps             []CompositionStep            `json:"steps"`
	InputMapping      map[string]map[string]string `json:"input_mapping"`
	OutputMapping     map[string]string            `json:"output_mapping"`
	EmptyResultPolicy string                       `json:"empty_result_policy,omitempty"`
	EmptyResultOutput map[string]any               `json:"empty_result_output,omitempty"`
	FailurePolicy     FailurePolicy                `json:"failure_policy"`
	AuditPolicy       AuditPolicy                  `json:"audit_policy"`
}

type GrantPolicy struct {
	AllowedGrantTypes []string `json:"allowed_grant_types"`
	DefaultGrantType  string   `json:"default_grant_type"`
	ExpiresInSeconds  int      `json:"expires_in_seconds"`
	MaxUses           int      `json:"max_uses"`
}

type CapabilityInputFormalization struct {
	InputName         string                      `json:"input_name"`
	InputType         string                      `json:"input_type"`
	Required          bool                        `json:"required"`
	Summary           string                      `json:"summary"`
	DefaultValue      string                      `json:"default_value"`
	AllowedValues     []string                    `json:"allowed_values,omitempty"`
	SemanticType      string                      `json:"semantic_type,omitempty"`
	InputFormat       string                      `json:"input_format,omitempty"`
	ValidationPattern string                      `json:"validation_pattern,omitempty"`
	ClarificationHint string                      `json:"clarification_hint,omitempty"`
	EntityReference   bool                        `json:"entity_reference,omitempty"`
	CatalogRef        string                      `json:"catalog_ref,omitempty"`
	Resolution        *InputResolutionMetadata    `json:"resolution,omitempty"`
	SemanticAliases   []string                    `json:"semantic_aliases,omitempty"`
	InputMeanings     []InputMeaningFormalization `json:"input_meanings,omitempty"`
}

type InputResolutionMetadata struct {
	Mode         string `json:"mode"`
	ResolverRef  string `json:"resolver_ref,omitempty"`
	OnMissing    string `json:"on_missing,omitempty"`
	OnAmbiguous  string `json:"on_ambiguous,omitempty"`
	OnUnresolved string `json:"on_unresolved,omitempty"`
}

type InputMeaningFormalization struct {
	Label       string `json:"label"`
	Value       string `json:"value"`
	Description string `json:"description,omitempty"`
}

type PrincipalSelector struct {
	Claim  string `json:"claim,omitempty"`
	Equals string `json:"equals,omitempty"`
}

type PermissionIntentBinding struct {
	ID                    string   `json:"id,omitempty"`
	ActorID               string   `json:"actor_id,omitempty"`
	BusinessArea          string   `json:"business_area,omitempty"`
	BusinessAreaLabel     string   `json:"business_area_label,omitempty"`
	AccessPosture         string   `json:"access_posture,omitempty"`
	GovernedOutcomeType   string   `json:"governed_outcome_type,omitempty"`
	GovernedOutcome       string   `json:"governed_outcome,omitempty"`
	TargetServiceIDs      []string `json:"target_service_ids,omitempty"`
	TargetCapabilityIDs   []string `json:"target_capability_ids,omitempty"`
	FormalizationStrategy string   `json:"formalization_strategy,omitempty"`
}

type RuntimePolicyBinding struct {
	ID                 string            `json:"id,omitempty"`
	SourcePermissionID string            `json:"source_permission_id,omitempty"`
	ActorID            string            `json:"actor_id,omitempty"`
	PrincipalSelector  PrincipalSelector `json:"principal_selector,omitempty"`
	BusinessArea       string            `json:"business_area,omitempty"`
	BusinessAreaLabel  string            `json:"business_area_label,omitempty"`
	ServiceIDs         []string          `json:"service_ids,omitempty"`
	CapabilityIDs      []string          `json:"capability_ids,omitempty"`
	RequiredScopes     []string          `json:"required_scopes,omitempty"`
	Decision           string            `json:"decision,omitempty"`
	BusinessRule       string            `json:"business_rule,omitempty"`
	EnforcementNotes   string            `json:"enforcement_notes,omitempty"`
}

type IntegrationFrontingConfig struct {
	ProjectType        string                         `json:"project_type,omitempty"`
	CapabilityMappings []IntegrationCapabilityMapping `json:"capability_mappings,omitempty"`
}

type IntegrationCapabilityMapping struct {
	ID                            string                      `json:"id,omitempty"`
	CapabilityID                  string                      `json:"capability_id"`
	Title                         string                      `json:"title,omitempty"`
	Intent                        string                      `json:"intent,omitempty"`
	ServiceID                     string                      `json:"service_id"`
	ServiceName                   string                      `json:"service_name,omitempty"`
	BackendKind                   string                      `json:"backend_kind"`
	ConnectionRef                 string                      `json:"connection_ref"`
	RawOperationRefs              []string                    `json:"raw_operation_refs"`
	BackendBindings               []IntegrationBackendBinding `json:"backend_bindings,omitempty"`
	ExecutionPosture              string                      `json:"execution_posture"`
	SideEffectLevel               string                      `json:"side_effect_level"`
	SubjectKind                   string                      `json:"subject_kind,omitempty"`
	ContextType                   string                      `json:"context_type,omitempty"`
	OutputIntent                  string                      `json:"output_intent,omitempty"`
	RequiredInputs                []string                    `json:"required_inputs,omitempty"`
	OptionalInputs                []string                    `json:"optional_inputs,omitempty"`
	BackendInputMode              string                      `json:"backend_input_mode,omitempty"`
	DerivedRequiredBackendInputs  []string                    `json:"derived_required_backend_inputs,omitempty"`
	DerivedOptionalBackendInputs  []string                    `json:"derived_optional_backend_inputs,omitempty"`
	ExplicitRequiredBackendInputs []string                    `json:"explicit_required_backend_inputs,omitempty"`
	ExplicitOptionalBackendInputs []string                    `json:"explicit_optional_backend_inputs,omitempty"`
	ApprovalRuleRefs              []string                    `json:"approval_rule_refs,omitempty"`
	DenialRuleRefs                []string                    `json:"denial_rule_refs,omitempty"`
	ClarificationRuleRefs         []string                    `json:"clarification_rule_refs,omitempty"`
	AuditRequired                 bool                        `json:"audit_required,omitempty"`
	OutboundControls              map[string]any              `json:"outbound_controls,omitempty"`
}

type IntegrationBackendBinding struct {
	BackendKind                   string   `json:"backend_kind"`
	ConnectionRef                 string   `json:"connection_ref"`
	RawOperationRefs              []string `json:"raw_operation_refs"`
	BackendInputMode              string   `json:"backend_input_mode,omitempty"`
	DerivedRequiredBackendInputs  []string `json:"derived_required_backend_inputs,omitempty"`
	DerivedOptionalBackendInputs  []string `json:"derived_optional_backend_inputs,omitempty"`
	ExplicitRequiredBackendInputs []string `json:"explicit_required_backend_inputs,omitempty"`
	ExplicitOptionalBackendInputs []string `json:"explicit_optional_backend_inputs,omitempty"`
	MatchedDiscoveryRecordIDs     []string `json:"matched_discovery_record_ids,omitempty"`
	Status                        string   `json:"status,omitempty"`
	StatusDetail                  string   `json:"status_detail,omitempty"`
}

type BuildTypeScriptProjectOptions struct {
	DependencySource DependencySource
	HttpRuntime      HttpRuntime
	Transports       []Transport
	PackageName      string
	Port             int
}

type BuildGoProjectOptions struct {
	DependencySource DependencySource
	Transports       []Transport
	ModulePath       string
	Port             int
}

type BuildPythonProjectOptions struct {
	DependencySource DependencySource
	Transports       []Transport
	ProjectName      string
	PackageName      string
	Port             int
}

type BuildJavaProjectOptions struct {
	DependencySource DependencySource
	Framework        JavaFramework
	Transports       []Transport
	ArtifactID       string
	PackageName      string
	Port             int
}

type BuildCSharpProjectOptions struct {
	DependencySource DependencySource
	Transports       []Transport
	ProjectName      string
	RootNamespace    string
	Port             int
}

type GeneratedProject struct {
	PackageName                string
	SystemName                 string
	Framework                  string
	Transports                 []string
	Services                   []GeneratedServiceMetadata
	CustomBundleTemplateValues map[string]string
	Files                      []GeneratedFile
}

type GeneratedFile struct {
	Path    string
	Content string
}
