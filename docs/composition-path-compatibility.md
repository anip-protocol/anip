# Composition Path Compatibility: Go v0.23

## Status

This note characterizes Go behavior at ANIP revision
`8263c68a2977d4a4e1a428d1d1e26a92a5f61659`. It changes neither the specification
nor production code. Passing the accompanying tests establishes implementation
behavior, not protocol conformance or compatibility with other SDKs.

There is an unresolved mismatch: the specification describes single-segment
property access, while the Go implementation accepts nested dotted properties.
Whether to narrow the implementation or revise the specification is a separate
compatibility decision. This note makes neither change.

## Specification And Implementation

The reviewed [SPEC input/output mapping section](../SPEC.md#input-and-output-mapping)
describes `$.input.X` and `$.steps.<id>.output.Y`, restricts JSONPath to
single-segment property access, and excludes filters, wildcards and recursion.
References to steps that do not precede the consuming step are rejected.

The Go parser in [service/v023.go](../packages/go/service/v023.go) instead permits
one or more property segments after the input root or step-output root:

```go
jsonpathInputRE = regexp.MustCompile(`^\$\.input(?:\.[A-Za-z_][A-Za-z0-9_]*)+$`)
jsonpathStepRE  = regexp.MustCompile(`^\$\.steps\.([A-Za-z_][A-Za-z0-9_-]*)\.output(?:\.[A-Za-z_][A-Za-z0-9_]*)+$`)
```

The repeated segment group permits paths such as `$.input.customer.address.city`
and `$.steps.select.output.result.items`. `resolveJsonPath` traverses those
segments as object keys. `ExecuteComposition` uses that resolver for child
arguments, and `buildOutput` uses it for the parent's mapped output.

| Form | Observed Go behavior |
| --- | --- |
| Nested parent input | Accepted and resolved through nested objects. |
| Nested output from an earlier step | Accepted and passed to a later step. |
| Nested parent output mapping | Accepted and resolved into the parent response. |
| Flat, single-segment properties | Still accepted and resolved. |
| Forward step references in input mappings | Rejected with `composition_invalid_step`. |
| Brackets, wildcards, filters and recursive descent | Rejected as malformed paths. |

Allowing dotted nested properties does not make this a general JSONPath engine.
Array subscripts, selectors and recursive traversal are not supported. Existing
missing-value, null, declaration-membership and failure-policy behavior is outside
the proposed change; this characterization does not tighten or endorse it.

## Executable Evidence

The accompanying
[composition_path_compatibility_test.go](../packages/go/service/composition_path_compatibility_test.go)
contains the executable characterization. The document does not maintain a
second, untested copy of the suite.

| Test | What it checks |
| --- | --- |
| `TestValidateCompositionRejectsUnsupportedPathForms` | Input mapping rejects forward references and the unsupported path forms. |
| `TestValidateCompositionOutputMappingRejectsUnsupportedForms` | Output mapping rejects malformed path forms. |
| `TestValidateCompositionAcceptsNestedMultiSegmentPathsGoBehavior` | Validation accepts nested input and step-output properties. |
| `TestExecuteCompositionNestedPathsFlowInputStepOutputAndOutputMapping` | Public execution preserves exact child arguments and final values through nested mappings. |
| `TestExecuteCompositionFlatSingleSegmentPathsPreserved` | Public execution preserves the existing flat-path behavior. |

These tests call `ValidateComposition` and `ExecuteComposition`; they do not
replace those production functions or merely test a duplicate parser. They
complement the existing [composition suite](../packages/go/service/v023_composition_test.go).

From the `packages/go` module directory, run the full service suite:

```sh
go test -json -mod=readonly ./service -count=1 -timeout=3m
```

To select only this file's five top-level tests, use their exact names:

```sh
go test ./service -count=1 -run '^(TestValidateCompositionRejectsUnsupportedPathForms|TestValidateCompositionOutputMappingRejectsUnsupportedForms|TestValidateCompositionAcceptsNestedMultiSegmentPathsGoBehavior|TestExecuteCompositionNestedPathsFlowInputStepOutputAndOutputMapping|TestExecuteCompositionFlatSingleSegmentPathsPreserved)$'
```

Neither a zero exit code nor a filtered command alone proves that new tests ran.
Inspect the JSON run/pass events for the expected test names and preserve any
skips or failures when reporting results.

## Compatibility Decision

The specification remains the normative reference. The tests intentionally
document the current implementation's broader segment support rather than
silently declaring that behavior conformant.

A later decision to revise the specification or narrow Go behavior needs an
explicit compatibility assessment, including relevant consumers and other SDKs.
This change does not claim Python, TypeScript or any other implementation behaves
the same way, and does not amend `SPEC.md` or any production source.
