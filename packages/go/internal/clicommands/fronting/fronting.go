package fronting

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"regexp"
	"strings"

	"github.com/anip-protocol/anip/packages/go/generator"
)

var (
	identifierPattern = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$`)
	capabilityPattern = regexp.MustCompile(`^[a-z][a-z0-9_]*(?:[._][a-z0-9_]+)+$`)
)

type cliError struct {
	message string
	code    int
}

type Starter struct {
	SchemaVersion string             `json:"schema_version"`
	SystemName    string             `json:"system_name"`
	DomainName    string             `json:"domain_name"`
	ServiceID     string             `json:"service_id"`
	ServiceName   string             `json:"service_name"`
	BackendKind   string             `json:"backend_kind"`
	ConnectionRef string             `json:"connection_ref"`
	Operations    []StarterOperation `json:"operations"`
}

type StarterOperation struct {
	CapabilityID     string         `json:"capability_id"`
	Title            string         `json:"title"`
	Summary          string         `json:"summary"`
	SubjectKind      string         `json:"subject_kind"`
	ContextType      string         `json:"context_type"`
	OutputIntent     string         `json:"output_intent"`
	BackendKind      string         `json:"backend_kind"`
	ConnectionRef    string         `json:"connection_ref"`
	Method           string         `json:"method"`
	Path             string         `json:"path"`
	RawOperationRefs []string       `json:"raw_operation_refs"`
	SideEffectLevel  string         `json:"side_effect_level"`
	BackendInputMode string         `json:"backend_input_mode"`
	Inputs           []StarterInput `json:"inputs"`
}

type StarterInput struct {
	Name              string                             `json:"name"`
	Type              string                             `json:"type"`
	Required          bool                               `json:"required"`
	Summary           string                             `json:"summary"`
	DefaultValue      string                             `json:"default_value"`
	AllowedValues     []string                           `json:"allowed_values"`
	SemanticType      string                             `json:"semantic_type"`
	ValidationPattern string                             `json:"validation_pattern"`
	ClarificationHint string                             `json:"clarification_hint"`
	EntityReference   bool                               `json:"entity_reference"`
	CatalogRef        string                             `json:"catalog_ref"`
	Resolution        *generator.InputResolutionMetadata `json:"resolution"`
}

func Run(args []string, stdout io.Writer, stderr io.Writer) (exitCode int) {
	if stdout == nil {
		stdout = os.Stdout
	}
	if stderr == nil {
		stderr = os.Stderr
	}
	defer func() {
		if recovered := recover(); recovered != nil {
			if err, ok := recovered.(cliError); ok {
				fmt.Fprintln(stderr, err.message)
				exitCode = err.code
				return
			}
			panic(recovered)
		}
	}()

	if len(args) == 0 {
		printUsage(stderr)
		return 2
	}
	switch args[0] {
	case "scaffold":
		return runScaffold(args[1:], stdout, stderr)
	case "help", "-h", "--help":
		printUsage(stdout)
		return 0
	default:
		fmt.Fprintf(stderr, "unknown fronting command %q\n", args[0])
		printUsage(stderr)
		return 2
	}
}

func printUsage(writer io.Writer) {
	fmt.Fprintln(writer, `Usage:
  anip fronting scaffold [flags]

Commands:
  scaffold  Generate a governed ANIP fronting service scaffold from a starter JSON file.`)
}

func runScaffold(args []string, stdout io.Writer, stderr io.Writer) int {
	var starterPath string
	var target string
	var outputDir string
	var dependencySource string
	var transportList string
	var force bool
	var port int

	fs := flag.NewFlagSet("anip fronting scaffold", flag.ContinueOnError)
	if hasHelpFlag(args) {
		fs.SetOutput(stdout)
	} else {
		fs.SetOutput(stderr)
	}
	fs.Usage = func() {
		writer := fs.Output()
		fmt.Fprintln(writer, `Usage:
  anip fronting scaffold --starter <starter.json> --target <language> --output <dir> [flags]

The starter file is reviewed implementation intent, not package behavior truth.
The command converts it into a normal ANIP Service Definition and generated
service scaffold with integration-fronting mapping artifacts.

Flags:`)
		fs.PrintDefaults()
	}
	fs.StringVar(&starterPath, "starter", "", "Path to an anip-fronting-starter/v0 JSON file")
	fs.StringVar(&target, "target", "python", "Target language: python, typescript, go, java, or csharp")
	fs.StringVar(&outputDir, "output", "", "Output directory")
	fs.StringVar(&dependencySource, "dependency-source", "local", "Dependency source: local or registry")
	fs.StringVar(&transportList, "transport", "http", "Transport list: http, stdio, or http,stdio")
	fs.BoolVar(&force, "force", false, "Overwrite output directory")
	fs.IntVar(&port, "port", 9100, "Generated service port")
	if err := fs.Parse(args); err != nil {
		if err == flag.ErrHelp {
			return 0
		}
		return 2
	}
	if strings.TrimSpace(starterPath) == "" {
		fail("--starter is required", 2)
	}
	if strings.TrimSpace(outputDir) == "" {
		fail("--output is required", 2)
	}

	starterBytes, err := os.ReadFile(starterPath)
	if err != nil {
		fail(fmt.Sprintf("read starter: %v", err), 1)
	}
	var starter Starter
	if err := json.Unmarshal(starterBytes, &starter); err != nil {
		fail(fmt.Sprintf("decode starter: %v", err), 1)
	}
	definition, err := buildDefinition(starter, starterBytes)
	if err != nil {
		fail(err.Error(), 2)
	}
	transports, err := generator.ParseTransportList(transportList)
	if err != nil {
		fail(err.Error(), 2)
	}
	project, err := buildProject(target, definition, generator.DependencySource(dependencySource), transports, port)
	if err != nil {
		fail(err.Error(), 1)
	}
	if err := generator.WriteGeneratedProject(project, outputDir, force); err != nil {
		fail(err.Error(), 1)
	}
	fmt.Fprintf(stdout, "wrote fronting scaffold: %s\n", outputDir)
	return 0
}

func buildDefinition(starter Starter, starterBytes []byte) (*generator.AnipServiceDefinition, error) {
	if starter.SchemaVersion != "" && starter.SchemaVersion != "anip-fronting-starter/v0" {
		return nil, fmt.Errorf("starter schema_version must be anip-fronting-starter/v0")
	}
	systemName := requiredIdentifier(starter.SystemName, "system_name")
	serviceID := requiredIdentifier(firstNonEmpty(starter.ServiceID, starter.SystemName), "service_id")
	serviceName := firstNonEmpty(starter.ServiceName, titleize(serviceID))
	domainName := firstNonEmpty(starter.DomainName, "integration_fronting")
	backendKind := firstNonEmpty(starter.BackendKind, "native_api")
	connectionRef := firstNonEmpty(starter.ConnectionRef, serviceID+"_connection")
	if len(starter.Operations) == 0 {
		return nil, fmt.Errorf("starter operations are required")
	}

	capabilityIDs := make([]string, 0, len(starter.Operations))
	formalizations := make([]generator.CapabilityFormalization, 0, len(starter.Operations))
	mappings := make([]generator.IntegrationCapabilityMapping, 0, len(starter.Operations))
	for index, operation := range starter.Operations {
		capabilityID, err := requiredCapabilityID(operation.CapabilityID, fmt.Sprintf("operations[%d].capability_id", index))
		if err != nil {
			return nil, err
		}
		capabilityIDs = append(capabilityIDs, capabilityID)
		inputs := buildInputs(operation.Inputs)
		requiredInputs, optionalInputs := inputNamesByRequired(inputs)
		sideEffect := firstNonEmpty(operation.SideEffectLevel, inferSideEffect(operation.Method))
		operationType := inferOperationType(sideEffect, operation.Method)
		rawOperationRefs := operation.RawOperationRefs
		if len(rawOperationRefs) == 0 && strings.TrimSpace(operation.Method) != "" && strings.TrimSpace(operation.Path) != "" {
			rawOperationRefs = []string{operationRefFor(operation.Method, operation.Path)}
		}
		if len(rawOperationRefs) == 0 {
			return nil, fmt.Errorf("operations[%d] must include raw_operation_refs or method/path", index)
		}

		formalizations = append(formalizations, generator.CapabilityFormalization{
			ID:               "cap-" + strings.ReplaceAll(capabilityID, ".", "-"),
			Kind:             "atomic",
			SourceKind:       "integration_fronting_source_doc",
			ServiceID:        serviceID,
			CapabilityID:     capabilityID,
			Title:            firstNonEmpty(operation.Title, titleize(capabilityID)),
			Summary:          firstNonEmpty(operation.Summary, "Governed fronting capability for "+capabilityID+"."),
			SubjectKind:      firstNonEmpty(operation.SubjectKind, "fronted_resource"),
			ContextType:      firstNonEmpty(operation.ContextType, "fronting_context"),
			OutputIntent:     firstNonEmpty(operation.OutputIntent, "governed_fronting_result"),
			IntentType:       inferIntentType(sideEffect),
			OperationType:    operationType,
			SideEffectLevel:  sideEffect,
			BackendOperation: strings.ReplaceAll(capabilityID, ".", "_"),
			PathTemplate:     firstNonEmpty(operation.Path, "/"+strings.ReplaceAll(capabilityID, ".", "/")),
			OutputShape:      strings.ReplaceAll(capabilityID, ".", "_") + "_result",
			Inputs:           inputs,
			GrantPolicy:      grantPolicyFor(sideEffect),
		})
		mappings = append(mappings, generator.IntegrationCapabilityMapping{
			ID:                    "map-" + strings.ReplaceAll(capabilityID, ".", "-"),
			CapabilityID:          capabilityID,
			Title:                 firstNonEmpty(operation.Title, titleize(capabilityID)),
			Intent:                firstNonEmpty(operation.Summary, "Governed fronting capability for "+capabilityID+"."),
			ServiceID:             serviceID,
			ServiceName:           serviceName,
			BackendKind:           firstNonEmpty(operation.BackendKind, backendKind),
			ConnectionRef:         firstNonEmpty(operation.ConnectionRef, connectionRef),
			RawOperationRefs:      rawOperationRefs,
			ExecutionPosture:      inferIntentType(sideEffect),
			SideEffectLevel:       sideEffect,
			SubjectKind:           firstNonEmpty(operation.SubjectKind, "fronted_resource"),
			ContextType:           firstNonEmpty(operation.ContextType, "fronting_context"),
			OutputIntent:          firstNonEmpty(operation.OutputIntent, "governed_fronting_result"),
			RequiredInputs:        requiredInputs,
			OptionalInputs:        optionalInputs,
			BackendInputMode:      firstNonEmpty(operation.BackendInputMode, "hybrid"),
			AuditRequired:         true,
			OutboundControls:      map[string]any{"redaction_required": true, "raw_backend_not_agent_visible": true},
			ClarificationRuleRefs: []string{"missing_required_inputs"},
		})
	}
	sum := sha256.Sum256(starterBytes)
	return &generator.AnipServiceDefinition{
		ArtifactType:          "anip_service_definition",
		ContractSchemaVersion: "anip-service-definition/v1",
		CompiledContractIdentity: &generator.CompiledContractIdentity{
			Signature:          "sha256:" + hex.EncodeToString(sum[:]),
			SignatureAlgorithm: "sha256",
		},
		Identity: &generator.ServiceIdentity{
			SystemName:        systemName,
			DomainName:        domainName,
			DeliveryModel:     "governed_integration_fronting",
			ArchitectureShape: "single_service",
		},
		Authority: &generator.AuthorityConfig{
			ApprovalExpectation:   "approval_gated_for_write_like_actions",
			BlockedFailurePosture: "clarify_or_stop",
		},
		Audit: &generator.AuditConfig{
			DurableRecordsRequired:    true,
			SearchableHistoryRequired: true,
		},
		Generation: &generator.GenerationConfig{
			Protocols:          []string{"https"},
			LayoutStrategy:     "single_package",
			SelectedServiceIDs: []string{serviceID},
		},
		ServiceTopologyBindings: []generator.ServiceTopologyBinding{{
			ID:                      "svc-" + serviceID,
			ServiceID:               serviceID,
			ServiceName:             serviceName,
			SourceRole:              "integration_fronting",
			SourceCapabilities:      capabilityIDs,
			FormalizedCapabilityIDs: capabilityIDs,
			OwnedConceptIDs:         []string{"fronted_resource"},
		}},
		CapabilityFormalizations: formalizations,
		IntegrationFronting: &generator.IntegrationFrontingConfig{
			ProjectType:        "governed_api_fronting",
			CapabilityMappings: mappings,
		},
	}, nil
}

func buildProject(target string, definition *generator.AnipServiceDefinition, dependencySource generator.DependencySource, transports []generator.Transport, port int) (*generator.GeneratedProject, error) {
	switch strings.TrimSpace(target) {
	case "python":
		return generator.BuildPythonProject(definition, generator.BuildPythonProjectOptions{DependencySource: dependencySource, Transports: transports, Port: port})
	case "typescript":
		return generator.BuildTypeScriptProject(definition, generator.BuildTypeScriptProjectOptions{DependencySource: dependencySource, Transports: transports, Port: port})
	case "go":
		return generator.BuildGoProject(definition, generator.BuildGoProjectOptions{DependencySource: dependencySource, Transports: transports, Port: port})
	case "java":
		return generator.BuildJavaProject(definition, generator.BuildJavaProjectOptions{DependencySource: dependencySource, Transports: transports, Port: port})
	case "csharp":
		return generator.BuildCSharpProject(definition, generator.BuildCSharpProjectOptions{DependencySource: dependencySource, Transports: transports, Port: port})
	default:
		return nil, fmt.Errorf("--target must be python, typescript, go, java, or csharp")
	}
}

func buildInputs(starterInputs []StarterInput) []generator.CapabilityInputFormalization {
	inputs := make([]generator.CapabilityInputFormalization, 0, len(starterInputs))
	for _, input := range starterInputs {
		name := strings.TrimSpace(input.Name)
		if !identifierPattern.MatchString(name) {
			fail("starter input names must be lowercase identifiers", 2)
		}
		inputs = append(inputs, generator.CapabilityInputFormalization{
			InputName:         name,
			InputType:         firstNonEmpty(input.Type, "string"),
			Required:          input.Required,
			Summary:           firstNonEmpty(input.Summary, name),
			DefaultValue:      input.DefaultValue,
			AllowedValues:     input.AllowedValues,
			SemanticType:      input.SemanticType,
			ValidationPattern: input.ValidationPattern,
			ClarificationHint: input.ClarificationHint,
			EntityReference:   input.EntityReference,
			CatalogRef:        input.CatalogRef,
			Resolution:        input.Resolution,
		})
	}
	return inputs
}

func inputNamesByRequired(inputs []generator.CapabilityInputFormalization) ([]string, []string) {
	required := []string{}
	optional := []string{}
	for _, input := range inputs {
		if input.Required {
			required = append(required, input.InputName)
		} else {
			optional = append(optional, input.InputName)
		}
	}
	return required, optional
}

func requiredIdentifier(value string, field string) string {
	trimmed := strings.TrimSpace(value)
	if !identifierPattern.MatchString(trimmed) {
		fail(field+" must be a lowercase identifier", 2)
	}
	return trimmed
}

func requiredCapabilityID(value string, field string) (string, error) {
	trimmed := strings.TrimSpace(value)
	if !capabilityPattern.MatchString(trimmed) {
		return "", fmt.Errorf("%s must be a dotted lowercase capability id", field)
	}
	return trimmed, nil
}

func grantPolicyFor(sideEffect string) *generator.GrantPolicy {
	if sideEffect != "approval_required" && sideEffect != "write_adjacent" {
		return nil
	}
	return &generator.GrantPolicy{
		AllowedGrantTypes: []string{"one_time", "session_bound"},
		DefaultGrantType:  "one_time",
		ExpiresInSeconds:  900,
		MaxUses:           1,
	}
}

func inferSideEffect(method string) string {
	switch strings.ToUpper(strings.TrimSpace(method)) {
	case "POST", "PUT", "PATCH", "DELETE":
		return "approval_required"
	default:
		return "read_only"
	}
}

func inferOperationType(sideEffect string, method string) string {
	if sideEffect == "approval_required" || sideEffect == "write_adjacent" {
		return "write"
	}
	if strings.EqualFold(method, "POST") {
		return "write"
	}
	return "read"
}

func inferIntentType(sideEffect string) string {
	if sideEffect == "approval_required" || sideEffect == "write_adjacent" {
		return "prepare_only"
	}
	return "read_only"
}

func operationRefFor(method string, path string) string {
	value := strings.ToLower(strings.TrimSpace(method) + "_" + strings.TrimSpace(path))
	replacer := strings.NewReplacer("/", "_", "{", "", "}", "", "-", "_", ".", "_", ":", "_")
	value = replacer.Replace(value)
	value = strings.Trim(value, "_")
	value = regexp.MustCompile(`_+`).ReplaceAllString(value, "_")
	if value == "" || !identifierPattern.MatchString(value) {
		return "backend_operation"
	}
	return value
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if trimmed := strings.TrimSpace(value); trimmed != "" {
			return trimmed
		}
	}
	return ""
}

func titleize(value string) string {
	parts := strings.FieldsFunc(value, func(r rune) bool {
		return r == '.' || r == '_' || r == '-'
	})
	for index, part := range parts {
		if part == "" {
			continue
		}
		parts[index] = strings.ToUpper(part[:1]) + part[1:]
	}
	return strings.Join(parts, " ")
}

func hasHelpFlag(args []string) bool {
	for _, arg := range args {
		if arg == "-h" || arg == "--help" {
			return true
		}
	}
	return false
}

func fail(message string, code int) {
	panic(cliError{message: message, code: code})
}
