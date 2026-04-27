using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Anip.Core;
using Anip.Crypto;
using Anip.Server;

namespace Anip.Service;

/// <summary>
/// v0.23 — Capability composition + approval grants runtime helpers.
/// Mirrors <c>packages/python/anip-service/src/anip_service/v023.py</c> and
/// <c>packages/java/anip-service/src/main/java/dev/anip/service/V023.java</c>:
/// composition validation, composition execution, SHA-256 digests over
/// canonical JSON, approval grant signing/verification (detached JWS over
/// canonical grant payload, byte-for-byte identical to the other runtimes),
/// continuation grant validation, and ApprovalRequest materialization.
/// </summary>
public static class V023
{
    private static readonly JsonSerializerOptions s_serializer = new()
    {
        DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull,
    };

    private static readonly Regex s_inputPath =
        new(@"^\$\.input(?:\.[A-Za-z_][A-Za-z0-9_]*)+$", RegexOptions.Compiled);

    private static readonly Regex s_stepPath =
        new(@"^\$\.steps\.([A-Za-z_][A-Za-z0-9_-]*)\.output(?:\.[A-Za-z_][A-Za-z0-9_]*)+$",
            RegexOptions.Compiled);

    // -----------------------------------------------------------------------
    // ID + time helpers
    // -----------------------------------------------------------------------

    public static string NewApprovalRequestId() => "apr_" + RandomHex(6);

    public static string NewGrantId() => "grant_" + RandomHex(6);

    private static string RandomHex(int bytes)
    {
        var b = new byte[bytes];
        RandomNumberGenerator.Fill(b);
        return Convert.ToHexString(b).ToLowerInvariant();
    }

    public static string UtcNowIso() =>
        DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffffffZ", CultureInfo.InvariantCulture);

    public static string UtcInIso(int seconds) =>
        DateTime.UtcNow.AddSeconds(seconds)
            .ToString("yyyy-MM-ddTHH:mm:ss.fffffffZ", CultureInfo.InvariantCulture);

    // -----------------------------------------------------------------------
    // Canonical JSON + SHA-256 digest
    // -----------------------------------------------------------------------

    /// <summary>
    /// Serializes a value with recursively sorted keys, no whitespace.
    /// Matches Python's <c>json.dumps(value, sort_keys=True, separators=(",", ":"))</c>
    /// byte-for-byte and TS / Go / Java <c>canonicalJson</c> — load-bearing for
    /// cross-runtime grant verification.
    /// </summary>
    public static string CanonicalJson(object? value)
    {
        var sb = new StringBuilder();
        CanonicalEncode(sb, Normalize(value));
        return sb.ToString();
    }

    private static object? Normalize(object? value)
    {
        if (value == null) return null;
        // Roundtrip through STJ to canonicalise property names + collapse types
        // into JsonElement-friendly primitives.
        var json = JsonSerializer.Serialize(value, s_serializer);
        using var doc = JsonDocument.Parse(json);
        return ToCanonicalNode(doc.RootElement.Clone());
    }

    private static object? ToCanonicalNode(JsonElement el)
    {
        switch (el.ValueKind)
        {
            case JsonValueKind.Null:
                return null;
            case JsonValueKind.True:
                return true;
            case JsonValueKind.False:
                return false;
            case JsonValueKind.String:
                return el.GetString();
            case JsonValueKind.Number:
                if (el.TryGetInt64(out var l)) return l;
                return el.GetDouble();
            case JsonValueKind.Array:
                {
                    var list = new List<object?>();
                    foreach (var item in el.EnumerateArray())
                    {
                        list.Add(ToCanonicalNode(item));
                    }
                    return list;
                }
            case JsonValueKind.Object:
                {
                    var dict = new SortedDictionary<string, object?>(StringComparer.Ordinal);
                    foreach (var prop in el.EnumerateObject())
                    {
                        dict[prop.Name] = ToCanonicalNode(prop.Value);
                    }
                    return dict;
                }
            default:
                return null;
        }
    }

    private static void CanonicalEncode(StringBuilder sb, object? v)
    {
        switch (v)
        {
            case null:
                sb.Append("null");
                return;
            case bool b:
                sb.Append(b ? "true" : "false");
                return;
            case string s:
                sb.Append(JsonSerializer.Serialize(s));
                return;
            case long l:
                sb.Append(l.ToString(CultureInfo.InvariantCulture));
                return;
            case int i:
                sb.Append(i.ToString(CultureInfo.InvariantCulture));
                return;
            case double d:
                if (double.IsFinite(d) && d == Math.Floor(d))
                {
                    // Match Python json.dumps: integer-valued floats keep `.0`.
                    sb.Append(d.ToString("R", CultureInfo.InvariantCulture));
                    if (!d.ToString("R", CultureInfo.InvariantCulture).Contains('.')
                        && !d.ToString("R", CultureInfo.InvariantCulture).Contains('e')
                        && !d.ToString("R", CultureInfo.InvariantCulture).Contains('E'))
                    {
                        sb.Append(".0");
                    }
                }
                else
                {
                    sb.Append(d.ToString("R", CultureInfo.InvariantCulture));
                }
                return;
            case IList<object?> list:
                sb.Append('[');
                for (var i2 = 0; i2 < list.Count; i2++)
                {
                    if (i2 > 0) sb.Append(',');
                    CanonicalEncode(sb, list[i2]);
                }
                sb.Append(']');
                return;
            case SortedDictionary<string, object?> sd:
                sb.Append('{');
                var first = true;
                foreach (var kv in sd)
                {
                    if (!first) sb.Append(',');
                    first = false;
                    sb.Append(JsonSerializer.Serialize(kv.Key));
                    sb.Append(':');
                    CanonicalEncode(sb, kv.Value);
                }
                sb.Append('}');
                return;
            default:
                sb.Append(JsonSerializer.Serialize(v, s_serializer));
                return;
        }
    }

    /// <summary>SHA-256 over canonical JSON, returns "sha256:&lt;hex&gt;".</summary>
    public static string Sha256Digest(object? value)
    {
        var payload = Encoding.UTF8.GetBytes(CanonicalJson(value));
        var hash = SHA256.HashData(payload);
        return "sha256:" + Convert.ToHexString(hash).ToLowerInvariant();
    }

    // -----------------------------------------------------------------------
    // Composition validation
    // -----------------------------------------------------------------------

    /// <summary>Thrown when a composed capability declaration violates a v0.23 invariant.</summary>
    public sealed class CompositionValidationError : Exception
    {
        public CompositionValidationError(string message) : base(message) { }
    }

    /// <summary>
    /// Enforces SPEC.md §4.6 invariants on a composed capability declaration.
    /// No-op when <c>decl.Kind != "composed"</c>.
    /// </summary>
    public static void ValidateComposition(string parentName,
                                           CapabilityDeclaration decl,
                                           IReadOnlyDictionary<string, CapabilityDeclaration> registry)
    {
        if (decl.Kind != "composed") return;
        var comp = decl.Composition;
        if (comp == null)
        {
            throw new CompositionValidationError(
                $"composition_invalid_step: capability '{parentName}' declares kind='composed' but composition is missing");
        }
        if (comp.AuthorityBoundary != "same_service")
        {
            throw new CompositionValidationError(
                $"composition_unsupported_authority_boundary: '{comp.AuthorityBoundary}' is reserved in v0.23");
        }
        if (comp.Steps == null || comp.Steps.Count == 0)
        {
            throw new CompositionValidationError("composition_invalid_step: composition has no steps");
        }

        var stepIndex = new Dictionary<string, int>();
        for (var i = 0; i < comp.Steps.Count; i++)
        {
            var s = comp.Steps[i];
            if (stepIndex.ContainsKey(s.Id))
            {
                throw new CompositionValidationError("composition_invalid_step: duplicate step ids");
            }
            stepIndex[s.Id] = i;
        }

        CompositionStep? sourceStep = null;
        foreach (var s in comp.Steps)
        {
            if (s.EmptyResultSource)
            {
                if (sourceStep != null)
                {
                    throw new CompositionValidationError(
                        "composition_invalid_step: at most one step may have empty_result_source=true");
                }
                sourceStep = s;
            }
        }

        foreach (var step in comp.Steps)
        {
            if (parentName == step.Capability)
            {
                throw new CompositionValidationError(
                    $"composition_invalid_step: step '{step.Id}' self-references parent capability");
            }
            if (!registry.TryGetValue(step.Capability, out var target))
            {
                throw new CompositionValidationError(
                    $"composition_unknown_capability: step '{step.Id}' references unknown capability '{step.Capability}'");
            }
            var kind = string.IsNullOrEmpty(target.Kind) ? "atomic" : target.Kind;
            if (kind != "atomic")
            {
                throw new CompositionValidationError(
                    $"composition_invalid_step: step '{step.Id}' references '{step.Capability}' which is kind='{kind}'; composed capabilities may only call kind='atomic' steps in v0.23");
            }
        }

        if (comp.InputMapping != null)
        {
            foreach (var kv in comp.InputMapping)
            {
                var stepKey = kv.Key;
                if (!stepIndex.TryGetValue(stepKey, out var stepPos))
                {
                    throw new CompositionValidationError(
                        $"composition_invalid_step: input_mapping key '{stepKey}' is not a declared step id");
                }
                foreach (var param in kv.Value)
                {
                    var refStep = ParseStepRef(param.Value);
                    if (refStep == null) continue;
                    if (!stepIndex.TryGetValue(refStep, out var refPos))
                    {
                        throw new CompositionValidationError(
                            $"composition_invalid_step: input_mapping[{stepKey}].{param.Key} references unknown step '{refStep}'");
                    }
                    if (refPos >= stepPos)
                    {
                        throw new CompositionValidationError(
                            $"composition_invalid_step: input_mapping[{stepKey}].{param.Key} forward-references '{refStep}' (forward-only references required)");
                    }
                }
            }
        }

        if (comp.OutputMapping != null)
        {
            foreach (var kv in comp.OutputMapping)
            {
                var refStep = ParseStepRef(kv.Value);
                if (refStep == null) continue;
                if (!stepIndex.ContainsKey(refStep))
                {
                    throw new CompositionValidationError(
                        $"composition_invalid_step: output_mapping['{kv.Key}'] references unknown step '{refStep}'");
                }
            }
        }

        if (sourceStep != null && string.IsNullOrEmpty(comp.EmptyResultPolicy))
        {
            throw new CompositionValidationError(
                "composition_invalid_step: step has empty_result_source=true but composition has no empty_result_policy");
        }

        var policy = comp.EmptyResultPolicy;
        if (policy == "return_success_no_results")
        {
            if (comp.EmptyResultOutput == null)
            {
                throw new CompositionValidationError(
                    "composition_invalid_step: empty_result_policy='return_success_no_results' requires empty_result_output");
            }
            if (sourceStep == null)
            {
                throw new CompositionValidationError(
                    "composition_invalid_step: empty_result_output requires a step with empty_result_source=true");
            }
            foreach (var kv in comp.EmptyResultOutput)
            {
                if (kv.Value is string sv && sv.StartsWith("$", StringComparison.Ordinal))
                {
                    var refStep = ParseStepRef(sv);
                    if (refStep != null && refStep != sourceStep.Id)
                    {
                        throw new CompositionValidationError(
                            $"composition_invalid_step: empty_result_output['{kv.Key}'] references step '{refStep}' but only the empty_result_source step '{sourceStep.Id}' (or $.input.*) is allowed");
                    }
                }
            }
        }
        else if ((policy == "clarify" || policy == "deny") && comp.EmptyResultOutput != null)
        {
            throw new CompositionValidationError(
                $"composition_invalid_step: empty_result_output is forbidden when empty_result_policy='{policy}'");
        }
    }

    private static string? ParseStepRef(string path)
    {
        if (s_inputPath.IsMatch(path)) return null;
        var m = s_stepPath.Match(path);
        if (!m.Success)
        {
            throw new CompositionValidationError(
                $"composition_invalid_step: malformed JSONPath '{path}' (must be $.input.* or $.steps.<id>.output.*)");
        }
        return m.Groups[1].Value;
    }

    // -----------------------------------------------------------------------
    // Composition execution
    // -----------------------------------------------------------------------

    /// <summary>Invokes a child capability with the parent's authority/audit lineage.</summary>
    public delegate Dictionary<string, object?> InvokeStepFunc(
        string capability, Dictionary<string, object?> parameters);

    /// <summary>
    /// Runs a composed capability's steps and returns the parent response body.
    /// Throws <see cref="AnipError"/> on policy-driven failures.
    /// </summary>
    public static Dictionary<string, object?> ExecuteComposition(
        string parentName,
        CapabilityDeclaration decl,
        Dictionary<string, object?> parentInput,
        InvokeStepFunc invokeStep)
    {
        var comp = decl.Composition
            ?? throw new InvalidOperationException($"capability '{parentName}' has no composition");
        CompositionStep? sourceStep = null;
        foreach (var s in comp.Steps)
        {
            if (s.EmptyResultSource) { sourceStep = s; break; }
        }

        var stepOutputs = new Dictionary<string, Dictionary<string, object?>>();
        foreach (var step in comp.Steps)
        {
            Dictionary<string, string> mapping = new();
            if (comp.InputMapping != null && comp.InputMapping.TryGetValue(step.Id, out var m))
            {
                mapping = m;
            }
            var stepInput = new Dictionary<string, object?>();
            foreach (var kv in mapping)
            {
                stepInput[kv.Key] = TryResolveJsonPath(kv.Value, parentInput, stepOutputs);
            }

            var result = invokeStep(step.Capability, stepInput);
            var success = result.TryGetValue("success", out var sv) && sv is true;
            if (!success)
            {
                Dictionary<string, object?> failure = new();
                if (result.TryGetValue("failure", out var fObj) && fObj is Dictionary<string, object?> fd)
                {
                    failure = fd;
                }
                var failureType = failure.TryGetValue("type", out var ft) ? ft as string ?? "unknown" : "unknown";
                var detail = failure.TryGetValue("detail", out var dt) ? dt as string ?? "child step failed" : "child step failed";
                var outcome = FailureOutcomeFor(failureType, comp.FailurePolicy);
                if (outcome == "fail_parent")
                {
                    throw new AnipError(Constants.FailureCompositionChildFailed,
                        $"child step '{step.Id}' ({step.Capability}) failed with {failureType}: {detail}")
                        .WithResolution("contact_service_owner");
                }
                var propagated = new AnipError(failureType, detail);
                if (failure.TryGetValue("approval_required", out var apReqObj)
                    && apReqObj is Dictionary<string, object?> apReq)
                {
                    var meta = ApprovalMetadataFromMap(apReq);
                    if (meta != null) propagated.WithApprovalRequired(meta);
                }
                throw propagated;
            }

            Dictionary<string, object?> stepResult = new();
            if (result.TryGetValue("result", out var rObj) && rObj is Dictionary<string, object?> rd)
            {
                stepResult = rd;
            }
            stepOutputs[step.Id] = stepResult;

            if (sourceStep != null && step.Id == sourceStep.Id && IsEmptyForStep(step, stepResult))
            {
                return BuildEmptyResultResponse(comp, parentInput, stepResult);
            }
        }
        return BuildOutput(comp.OutputMapping, parentInput, stepOutputs);
    }

    private static string FailureOutcomeFor(string failureType, FailurePolicy policy)
    {
        policy ??= new FailurePolicy();
        return failureType switch
        {
            "approval_required" => policy.ChildApprovalRequired,
            "scope_insufficient" or "denied" or "non_delegable_action" => policy.ChildDenial,
            "binding_missing" or "binding_stale" or "control_requirement_unsatisfied"
                or "purpose_mismatch" or "invalid_parameters" => policy.ChildClarification,
            _ => policy.ChildError,
        };
    }

    private static object? TryResolveJsonPath(string path,
                                              Dictionary<string, object?> parentInput,
                                              Dictionary<string, Dictionary<string, object?>> stepOutputs)
    {
        try
        {
            return ResolveJsonPath(path, parentInput, stepOutputs);
        }
        catch
        {
            return null;
        }
    }

    private static object? ResolveJsonPath(string path,
                                            Dictionary<string, object?> parentInput,
                                            Dictionary<string, Dictionary<string, object?>> stepOutputs)
    {
        if (s_inputPath.IsMatch(path))
        {
            var parts = path.Split('.');
            object? cur = parentInput;
            for (var i = 2; i < parts.Length; i++)
            {
                if (cur is not IDictionary<string, object?> obj)
                    throw new InvalidOperationException("not an object at " + path);
                if (!obj.TryGetValue(parts[i], out var next))
                    throw new InvalidOperationException($"missing key '{parts[i]}' at {path}");
                cur = next;
            }
            return cur;
        }
        var m = s_stepPath.Match(path);
        if (!m.Success) throw new InvalidOperationException("malformed JSONPath " + path);
        var stepId = m.Groups[1].Value;
        if (!stepOutputs.TryGetValue(stepId, out var output))
            throw new InvalidOperationException($"step '{stepId}' has no output");
        var ps = path.Split('.');
        object? cur2 = output;
        for (var i = 4; i < ps.Length; i++)
        {
            if (cur2 is not IDictionary<string, object?> obj)
                throw new InvalidOperationException("not an object at " + path);
            if (!obj.TryGetValue(ps[i], out var next))
                throw new InvalidOperationException($"missing key '{ps[i]}' at {path}");
            cur2 = next;
        }
        return cur2;
    }

    private static bool IsEmptyValue(object? v) => v switch
    {
        null => true,
        IList<object?> list => list.Count == 0,
        IDictionary<string, object?> dict => dict.Count == 0,
        string s => s.Length == 0,
        _ => false,
    };

    private static bool IsEmptyForStep(CompositionStep step, Dictionary<string, object?> output)
    {
        if (output == null || output.Count == 0) return true;
        if (!string.IsNullOrEmpty(step.EmptyResultPath))
        {
            var keys = step.EmptyResultPath.Split('.');
            object? cur = output;
            foreach (var k in keys)
            {
                if (k.Length == 0 || k == "$") continue;
                if (cur is not IDictionary<string, object?> obj) return true;
                if (!obj.TryGetValue(k, out var next) || next == null) return true;
                cur = next;
            }
            return IsEmptyValue(cur);
        }
        foreach (var v in output.Values)
        {
            if (v is IList<object?> l) return l.Count == 0;
        }
        foreach (var v in output.Values)
        {
            if (!IsEmptyValue(v)) return false;
        }
        return true;
    }

    private static Dictionary<string, object?> BuildOutput(
        Dictionary<string, string>? mapping,
        Dictionary<string, object?> parentInput,
        Dictionary<string, Dictionary<string, object?>> stepOutputs)
    {
        var result = new Dictionary<string, object?>();
        if (mapping == null) return result;
        foreach (var kv in mapping)
        {
            result[kv.Key] = TryResolveJsonPath(kv.Value, parentInput, stepOutputs);
        }
        return result;
    }

    private static Dictionary<string, object?> BuildEmptyResultResponse(
        Composition comp,
        Dictionary<string, object?> parentInput,
        Dictionary<string, object?> sourceOutput)
    {
        if (comp.EmptyResultPolicy == "clarify")
        {
            throw new AnipError("composition_empty_result_clarification_required",
                "selection step returned no results; clarification required");
        }
        if (comp.EmptyResultPolicy == "deny")
        {
            throw new AnipError("composition_empty_result_denied",
                "selection step returned no results; policy denies an empty answer");
        }
        var result = new Dictionary<string, object?>();
        if (comp.EmptyResultOutput == null) return result;
        foreach (var kv in comp.EmptyResultOutput)
        {
            if (kv.Value is string sv && sv.StartsWith("$", StringComparison.Ordinal))
            {
                result[kv.Key] = TryResolveEmptyRef(sv, parentInput, sourceOutput);
            }
            else
            {
                result[kv.Key] = kv.Value;
            }
        }
        return result;
    }

    private static object? TryResolveEmptyRef(string path,
                                              Dictionary<string, object?> parentInput,
                                              Dictionary<string, object?> sourceOutput)
    {
        try
        {
            if (s_inputPath.IsMatch(path))
            {
                return ResolveJsonPath(path, parentInput,
                    new Dictionary<string, Dictionary<string, object?>>());
            }
            var m = s_stepPath.Match(path);
            if (!m.Success) return null;
            var ps = path.Split('.');
            object? cur = sourceOutput;
            for (var i = 4; i < ps.Length; i++)
            {
                if (cur is not IDictionary<string, object?> obj) return null;
                if (!obj.TryGetValue(ps[i], out var next) || next == null) return null;
                cur = next;
            }
            return cur;
        }
        catch
        {
            return null;
        }
    }

    // -----------------------------------------------------------------------
    // Approval grant signing + verification
    // -----------------------------------------------------------------------

    /// <summary>
    /// Detached JWS signature over the canonical JSON of the grant excluding
    /// <c>signature</c> and <c>use_count</c>. v0.23 §4.8.
    /// </summary>
    public static string SignGrant(KeyManager km, ApprovalGrant grant)
    {
        var payload = GrantSigningPayload(grant);
        return JwsSigner.SignDetached(km.GetSigningKey(), km.GetSigningKid(), payload);
    }

    /// <summary>Returns true if the grant's signature is valid for the canonical payload.</summary>
    public static bool VerifyGrantSignature(KeyManager km, ApprovalGrant grant)
    {
        try
        {
            var payload = GrantSigningPayload(grant);
            return JwsSigner.VerifyDetached(km.GetSigningKey(), payload, grant.Signature);
        }
        catch
        {
            return false;
        }
    }

    private static byte[] GrantSigningPayload(ApprovalGrant grant)
    {
        var json = JsonSerializer.Serialize(grant, s_serializer);
        using var doc = JsonDocument.Parse(json);
        var sd = new SortedDictionary<string, object?>(StringComparer.Ordinal);
        foreach (var prop in doc.RootElement.EnumerateObject())
        {
            if (prop.Name == "signature" || prop.Name == "use_count") continue;
            sd[prop.Name] = ToCanonicalNode(prop.Value);
        }
        var sb = new StringBuilder();
        CanonicalEncode(sb, sd);
        return Encoding.UTF8.GetBytes(sb.ToString());
    }

    /// <summary>SPEC.md §4.8: every grant scope element must appear in the token's scope.</summary>
    public static bool GrantScopeSubsetOfToken(IList<string> grantScope, IList<string> tokenScope)
    {
        var set = new HashSet<string>(tokenScope, StringComparer.Ordinal);
        foreach (var s in grantScope)
        {
            if (!set.Contains(s)) return false;
        }
        return true;
    }

    // -----------------------------------------------------------------------
    // ApprovalRequest materialization (Phase 7.1)
    // -----------------------------------------------------------------------

    public sealed record ApprovalMaterialization(
        ApprovalRequiredMetadata Metadata,
        ApprovalRequest Request);

    /// <summary>
    /// Persists a fresh ApprovalRequest and returns the metadata + the persisted
    /// request. Storage failures propagate; the caller maps to service_unavailable
    /// per SPEC.md §4.7.
    /// </summary>
    public static ApprovalMaterialization MaterializeApprovalRequest(
        IStorage storage,
        CapabilityDeclaration decl,
        string parentInvocationId,
        Dictionary<string, object> requester,
        Dictionary<string, object> parameters,
        Dictionary<string, object> preview,
        GrantPolicy? serviceDefaultGrantPolicy)
    {
        var gp = decl.GrantPolicy ?? serviceDefaultGrantPolicy
            ?? throw new InvalidOperationException(
                $"capability '{decl.Name}' raised approval_required but has no grant_policy declared and no service-level default exists");

        var id = NewApprovalRequestId();
        var previewDigest = Sha256Digest(preview);
        var paramsDigest = Sha256Digest(parameters);
        var createdAt = UtcNowIso();
        var expiresAt = UtcInIso(gp.ExpiresInSeconds);
        var scope = decl.MinimumScope?.ToList() ?? new List<string>();
        var req = new ApprovalRequest
        {
            ApprovalRequestId = id,
            Capability = decl.Name,
            Scope = scope,
            Requester = requester,
            ParentInvocationId = parentInvocationId,
            Preview = preview,
            PreviewDigest = previewDigest,
            RequestedParameters = parameters,
            RequestedParametersDigest = paramsDigest,
            GrantPolicy = gp,
            Status = ApprovalRequest.StatusPending,
            CreatedAt = createdAt,
            ExpiresAt = expiresAt,
        };
        storage.StoreApprovalRequest(req);
        var metadata = new ApprovalRequiredMetadata
        {
            ApprovalRequestId = id,
            PreviewDigest = previewDigest,
            RequestedParametersDigest = paramsDigest,
            GrantPolicy = gp,
        };
        return new ApprovalMaterialization(metadata, req);
    }

    /// <summary>Best-effort rebuild of an ApprovalRequiredMetadata from a JSON-shaped map.</summary>
    public static ApprovalRequiredMetadata? ApprovalMetadataFromMap(IDictionary<string, object?> m)
    {
        if (m == null) return null;
        try
        {
            var id = m.TryGetValue("approval_request_id", out var idObj) ? idObj as string : null;
            if (string.IsNullOrEmpty(id)) return null;
            var previewDigest = m.TryGetValue("preview_digest", out var pdObj) ? pdObj as string ?? "" : "";
            var paramsDigest = m.TryGetValue("requested_parameters_digest", out var rpdObj) ? rpdObj as string ?? "" : "";
            GrantPolicy? gp = null;
            if (m.TryGetValue("grant_policy", out var gpObj))
            {
                if (gpObj is GrantPolicy g) gp = g;
                else if (gpObj is IDictionary<string, object?> gd)
                {
                    gp = new GrantPolicy();
                    if (gd.TryGetValue("allowed_grant_types", out var agt) && agt is IList<object?> al)
                        gp.AllowedGrantTypes = al.Select(x => x?.ToString() ?? "").ToList();
                    if (gd.TryGetValue("default_grant_type", out var dgt) && dgt is string dgs)
                        gp.DefaultGrantType = dgs;
                    if (gd.TryGetValue("expires_in_seconds", out var eis) && eis is IConvertible eisc)
                        gp.ExpiresInSeconds = eisc.ToInt32(CultureInfo.InvariantCulture);
                    if (gd.TryGetValue("max_uses", out var muObj) && muObj is IConvertible muc)
                        gp.MaxUses = muc.ToInt32(CultureInfo.InvariantCulture);
                }
            }
            return new ApprovalRequiredMetadata
            {
                ApprovalRequestId = id!,
                PreviewDigest = previewDigest,
                RequestedParametersDigest = paramsDigest,
                GrantPolicy = gp ?? new GrantPolicy(),
            };
        }
        catch
        {
            return null;
        }
    }

    // -----------------------------------------------------------------------
    // Continuation grant validation (Phase A read-side)
    // -----------------------------------------------------------------------

    /// <summary>Either the grant on success or a non-null FailureType on rejection.</summary>
    public sealed record ContinuationValidation(ApprovalGrant? Grant, string? FailureType)
    {
        public static ContinuationValidation Ok(ApprovalGrant g) => new(g, null);
        public static ContinuationValidation Fail(string reason) => new(null, reason);
    }

    /// <summary>
    /// Validates a continuation grant supplied with an invoke (read-side, Phase A).
    /// Atomic reservation is the caller's responsibility — see
    /// <see cref="IStorage.TryReserveGrant"/> for Phase B.
    /// Per SPEC.md §4.8, <paramref name="tokenSessionId"/> for session_bound
    /// grants MUST come from the signed delegation token, never from
    /// caller-supplied input.
    /// </summary>
    public static ContinuationValidation ValidateContinuationGrant(
        IStorage storage,
        KeyManager km,
        string grantId,
        string capability,
        Dictionary<string, object?> parameters,
        IList<string> tokenScope,
        string? tokenSessionId,
        string nowIso)
    {
        var grant = storage.GetGrant(grantId);
        if (grant == null) return ContinuationValidation.Fail(Constants.FailureGrantNotFound);
        if (!VerifyGrantSignature(km, grant))
        {
            return ContinuationValidation.Fail(Constants.FailureGrantNotFound);
        }
        if (!string.IsNullOrEmpty(grant.ExpiresAt) &&
            string.CompareOrdinal(grant.ExpiresAt, nowIso) <= 0)
        {
            return ContinuationValidation.Fail(Constants.FailureGrantExpired);
        }
        if (capability != grant.Capability)
        {
            return ContinuationValidation.Fail(Constants.FailureGrantCapabilityMismatch);
        }
        if (!GrantScopeSubsetOfToken(grant.Scope ?? new List<string>(), tokenScope ?? new List<string>()))
        {
            return ContinuationValidation.Fail(Constants.FailureGrantScopeMismatch);
        }
        // Coerce parameters to plain Dictionary<string, object?> to digest deterministically.
        var paramsForDigest = parameters != null
            ? (object)parameters
            : (object)new Dictionary<string, object?>();
        var submittedDigest = Sha256Digest(paramsForDigest);
        if (submittedDigest != grant.ApprovedParametersDigest)
        {
            return ContinuationValidation.Fail(Constants.FailureGrantParamDrift);
        }
        if (grant.GrantType == ApprovalGrant.TypeSessionBound)
        {
            if (string.IsNullOrEmpty(tokenSessionId) || tokenSessionId != grant.SessionId)
            {
                return ContinuationValidation.Fail(Constants.FailureGrantSessionInvalid);
            }
        }
        return ContinuationValidation.Ok(grant);
    }
}
