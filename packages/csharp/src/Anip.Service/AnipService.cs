using System.Text.Json;
using System.Threading.Channels;
using Anip.Core;
using Anip.Crypto;
using Anip.Server;

namespace Anip.Service;

/// <summary>
/// Main ANIP service runtime. Orchestrates core, crypto, and server into a usable service.
/// </summary>
public class AnipService : IDisposable
{
    private static readonly JsonSerializerOptions s_serializerOptions = new()
    {
        DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull
    };

    private readonly string _serviceId;
    private readonly string _trustLevel;
    private readonly Dictionary<string, CapabilityDef> _capabilities;
    private readonly Func<string, string?>? _authenticate;
    private readonly string _storageDsn;
    private readonly string? _keyPath;
    private readonly ObservabilityHooks? _hooks;
    private readonly CheckpointPolicy? _checkpointPolicy;
    private readonly int _retentionIntervalSeconds;
    private readonly RetentionPolicy _retentionPolicy;
    private readonly string _disclosureLevel;
    private readonly Dictionary<string, string>? _disclosurePolicy;
    private readonly AuditAggregator? _aggregator;

    private IStorage? _storage;
    private KeyManager? _keys;
    private DateTime _startedAt;
    private bool _retentionRunning;

    // Background task management
    private CancellationTokenSource? _cts;
    private readonly List<Task> _backgroundTasks = new();

    /// <summary>
    /// Creates a new AnipService from the given configuration.
    /// Call Start() to initialize storage and keys before use.
    /// </summary>
    public AnipService(ServiceConfig config)
    {
        _serviceId = config.ServiceId;

        _trustLevel = string.IsNullOrEmpty(config.Trust) ? "signed" : config.Trust;

        _capabilities = new Dictionary<string, CapabilityDef>();
        foreach (var cap in config.Capabilities)
        {
            _capabilities[cap.Declaration.Name] = cap;
        }

        // v0.23: validate composition invariants at registration time.
        var registry = _capabilities.ToDictionary(kv => kv.Key, kv => kv.Value.Declaration);
        foreach (var (name, cap) in _capabilities)
        {
            V023.ValidateComposition(name, cap.Declaration, registry);
        }

        _storageDsn = string.IsNullOrEmpty(config.Storage) ? ":memory:" : config.Storage;
        _keyPath = config.KeyPath;
        _authenticate = config.Authenticate;
        _hooks = config.Hooks;
        _checkpointPolicy = config.CheckpointPolicy;

        // Retention interval: 0 → default 60, negative → disabled (set to 0).
        var retentionInterval = config.RetentionIntervalSeconds;
        if (retentionInterval == 0)
            retentionInterval = 60;
        if (retentionInterval < 0)
            retentionInterval = 0;
        _retentionIntervalSeconds = retentionInterval;

        _retentionPolicy = config.RetentionPolicy ?? new RetentionPolicy();

        _disclosureLevel = string.IsNullOrEmpty(config.DisclosureLevel) ? "full" : config.DisclosureLevel;
        _disclosurePolicy = config.DisclosurePolicy;

        if (config.AggregationWindowSeconds > 0)
        {
            _aggregator = new AuditAggregator(config.AggregationWindowSeconds);
        }
    }

    /// <summary>The service identifier.</summary>
    public string ServiceId => _serviceId;

    /// <summary>
    /// Initializes storage, loads or generates cryptographic keys,
    /// and starts background workers for retention and checkpoint scheduling.
    /// </summary>
    public void Start()
    {
        InitStorage(_storageDsn, _keyPath);
        _startedAt = DateTime.UtcNow;
        _cts = new CancellationTokenSource();

        // Start retention enforcement.
        if (_retentionIntervalSeconds > 0)
        {
            _retentionRunning = true;
            _backgroundTasks.Add(Task.Run(() => RunRetentionLoop(_cts.Token)));
        }

        // Start checkpoint scheduling.
        if (_checkpointPolicy != null)
        {
            _backgroundTasks.Add(Task.Run(() => RunCheckpointLoop(_cts.Token)));
        }

        // Start aggregator flush.
        if (_aggregator != null)
        {
            _backgroundTasks.Add(Task.Run(() => RunAggregatorFlush(_cts.Token)));
        }
    }

    private void InitStorage(string storageDsn, string? keyPath)
    {
        if (storageDsn == ":memory:" || string.IsNullOrEmpty(storageDsn))
        {
            _storage = new SqliteStorage(":memory:");
        }
        else if (storageDsn.StartsWith("sqlite:///"))
        {
            var dbPath = storageDsn["sqlite:///".Length..];
            _storage = new SqliteStorage(dbPath);
        }
        else if (storageDsn.StartsWith("postgres://") || storageDsn.StartsWith("postgresql://"))
        {
            _storage = new NpgsqlStorage(storageDsn);
        }
        else
        {
            throw new InvalidOperationException($"unsupported storage: {storageDsn}");
        }

        _keys = new KeyManager(keyPath);
    }

    /// <summary>
    /// Stops background workers and releases storage resources.
    /// Safe to call multiple times.
    /// </summary>
    public void Shutdown()
    {
        if (_cts != null && !_cts.IsCancellationRequested)
        {
            _cts.Cancel();
            try
            {
                Task.WhenAll(_backgroundTasks).Wait(TimeSpan.FromSeconds(5));
            }
            catch (AggregateException)
            {
                // Background tasks may throw on cancellation.
            }
        }

        _storage?.Dispose();
        _storage = null;
    }

    public void Dispose()
    {
        Shutdown();
        _cts?.Dispose();
    }

    // --- Authentication ---

    /// <summary>
    /// Tries bootstrap authentication only (API keys, external auth).
    /// Returns the principal string or null.
    /// </summary>
    /// <remarks>
    /// The authentication hook is intentionally synchronous — it is called
    /// directly in the request path.  If your authentication requires async I/O,
    /// perform it before registering the hook or use a caching wrapper.
    /// C# does not support async hooks in this path.
    /// </remarks>
    public string? AuthenticateBearer(string bearer)
    {
        return _authenticate?.Invoke(bearer);
    }

    /// <summary>
    /// Verifies a JWT and returns the stored DelegationToken.
    /// Throws AnipError on failure.
    /// </summary>
    public DelegationToken ResolveBearerToken(string jwt)
    {
        try
        {
            var token = DelegationEngine.ResolveBearerToken(_keys!, _storage!, _serviceId, jwt);

            if (_hooks?.OnTokenResolved != null)
            {
                ObservabilityHooks.CallHook(() => _hooks.OnTokenResolved(token.TokenId, token.Subject));
            }

            return token;
        }
        catch (AnipError e)
        {
            if (_hooks?.OnAuthFailure != null)
            {
                ObservabilityHooks.CallHook(() => _hooks.OnAuthFailure(e.ErrorType, e.Detail));
            }
            throw;
        }
    }

    /// <summary>
    /// Issues a delegation token for the authenticated principal.
    /// </summary>
    public TokenResponse IssueToken(string principal, TokenRequest request)
    {
        var resp = DelegationEngine.IssueDelegationToken(_keys!, _storage!, _serviceId, principal, request);

        if (_hooks?.OnTokenIssued != null)
        {
            ObservabilityHooks.CallHook(() => _hooks.OnTokenIssued(resp.TokenId, principal, request.Capability));
        }

        return resp;
    }

    /// <summary>
    /// Issue a root token pre-bound to a specific capability.
    /// For delegated issuance, use <see cref="IssueDelegatedCapabilityToken"/> (v0.22).
    /// </summary>
    /// <remarks>
    /// <paramref name="scope"/> must be explicitly provided — capability names
    /// and scope strings are different things.
    /// </remarks>
    public TokenResponse IssueCapabilityToken(
        string principal,
        string capability,
        List<string> scope,
        Dictionary<string, object>? purposeParameters = null,
        int ttlHours = 2,
        Budget? budget = null)
    {
        var request = new TokenRequest
        {
            Subject = principal,
            Capability = capability,
            Scope = scope,
            PurposeParameters = purposeParameters,
            TtlHours = ttlHours,
            Budget = budget,
        };
        return IssueToken(principal, request);
    }

    /// <summary>
    /// Issue a delegated token from an existing parent token.
    /// <paramref name="parentToken"/> is a token ID (not a JWT) — the service looks up
    /// the parent by ID in storage. <paramref name="scope"/> must be explicitly provided.
    /// </summary>
    public TokenResponse IssueDelegatedCapabilityToken(
        string principal,
        string parentToken,
        string capability,
        List<string> scope,
        string subject,
        string? callerClass = null,
        Dictionary<string, object>? purposeParameters = null,
        int ttlHours = 2,
        Budget? budget = null)
    {
        var request = new TokenRequest
        {
            Subject = subject,
            Capability = capability,
            Scope = scope,
            ParentToken = parentToken,
            PurposeParameters = purposeParameters,
            TtlHours = ttlHours,
            CallerClass = callerClass,
            Budget = budget,
        };
        return IssueToken(principal, request);
    }

    // --- v0.23: ApprovalRequest + ApprovalGrant SPI ---

    /// <summary>
    /// Read-only pass-through to look up an ApprovalRequest by id. Returns null
    /// if not found. Used by the HTTP layer for SPEC.md §4.9 step 3.
    /// </summary>
    public ApprovalRequest? GetApprovalRequest(string approvalRequestId) =>
        _storage!.GetApprovalRequest(approvalRequestId);

    /// <summary>Returns the underlying storage handle. Test/SPI only.</summary>
    public IStorage GetStorage() => _storage!;

    /// <summary>
    /// Issues a signed ApprovalGrant for a pending ApprovalRequest. Atomic per
    /// SPEC.md §4.9 (Decision 0.9a) — clamps to grant_policy, signs, runs the
    /// atomic ApproveRequestAndStoreGrant primitive, emits an
    /// <c>approval_grant_issued</c> audit event.
    /// </summary>
    public ApprovalGrant IssueApprovalGrant(
        string approvalRequestId,
        string grantType,
        IDictionary<string, object?> approver,
        string? sessionId,
        int? expiresInSeconds,
        int? maxUses)
    {
        var request = _storage!.GetApprovalRequest(approvalRequestId)
            ?? throw new AnipError(Constants.FailureApprovalRequestNotFound,
                $"unknown approval_request_id={approvalRequestId}");

        if (request.Status != ApprovalRequest.StatusPending)
        {
            throw new AnipError(Constants.FailureApprovalRequestAlreadyDecided,
                $"approval_request_id={approvalRequestId} status={request.Status}");
        }
        var nowIso = V023.UtcNowIso();
        if (!string.IsNullOrEmpty(request.ExpiresAt) &&
            string.CompareOrdinal(request.ExpiresAt, nowIso) <= 0)
        {
            throw new AnipError(Constants.FailureApprovalRequestExpired,
                $"approval_request_id={approvalRequestId} expired at {request.ExpiresAt}");
        }
        var gp = request.GrantPolicy
            ?? throw new AnipError(Constants.FailureGrantTypeNotAllowed,
                "approval request has no grant_policy");
        if (!gp.AllowedGrantTypes.Contains(grantType))
        {
            throw new AnipError(Constants.FailureGrantTypeNotAllowed,
                $"grant_type={grantType} not in allowed_grant_types");
        }

        // SPEC §4.9: when supplied, expires_in_seconds and max_uses must be
        // positive integers. The HTTP route enforces this on body parsing,
        // but admin UIs / queue workers / tests call this SPI directly per
        // §4.9 line 1110, so we re-validate here.
        if (expiresInSeconds is int eis && eis < 1)
        {
            throw new AnipError(Constants.FailureInvalidParameters,
                $"expires_in_seconds must be a positive integer; got {eis}");
        }
        if (maxUses is int mu && mu < 1)
        {
            throw new AnipError(Constants.FailureInvalidParameters,
                $"max_uses must be a positive integer; got {mu}");
        }
        var effExpiresIn = expiresInSeconds ?? gp.ExpiresInSeconds;
        if (effExpiresIn > gp.ExpiresInSeconds)
        {
            throw new AnipError(Constants.FailureGrantTypeNotAllowed,
                $"expires_in_seconds={effExpiresIn} exceeds policy={gp.ExpiresInSeconds}");
        }
        var effMaxUses = maxUses ?? gp.MaxUses;
        if (grantType == ApprovalGrant.TypeOneTime)
        {
            effMaxUses = 1;
            if (!string.IsNullOrEmpty(sessionId))
            {
                throw new AnipError(Constants.FailureGrantTypeNotAllowed,
                    "one_time grants must not carry session_id");
            }
        }
        else if (grantType == ApprovalGrant.TypeSessionBound)
        {
            if (string.IsNullOrEmpty(sessionId))
            {
                throw new AnipError(Constants.FailureGrantTypeNotAllowed,
                    "session_bound grants require a session_id");
            }
        }
        if (effMaxUses > gp.MaxUses)
        {
            throw new AnipError(Constants.FailureGrantTypeNotAllowed,
                $"max_uses={effMaxUses} exceeds policy={gp.MaxUses}");
        }

        var grant = new ApprovalGrant
        {
            GrantId = V023.NewGrantId(),
            ApprovalRequestId = approvalRequestId,
            GrantType = grantType,
            Capability = request.Capability,
            Scope = new List<string>(request.Scope),
            ApprovedParametersDigest = request.RequestedParametersDigest,
            PreviewDigest = request.PreviewDigest,
            Requester = request.Requester,
            Approver = approver.ToDictionary(kv => kv.Key, kv => kv.Value!),
            IssuedAt = nowIso,
            ExpiresAt = V023.UtcInIso(effExpiresIn),
            MaxUses = effMaxUses,
            UseCount = 0,
            SessionId = sessionId,
        };
        try
        {
            grant.Signature = V023.SignGrant(_keys!, grant);
        }
        catch (Exception ex)
        {
            throw new AnipError(Constants.FailureInternalError,
                "grant signing failed: " + ex.Message);
        }

        var result = _storage!.ApproveRequestAndStoreGrant(
            approvalRequestId, grant, approver, nowIso, nowIso);
        if (!result.Ok)
        {
            var type = result.Reason switch
            {
                "approval_request_not_found" => Constants.FailureApprovalRequestNotFound,
                "approval_request_expired" => Constants.FailureApprovalRequestExpired,
                _ => Constants.FailureApprovalRequestAlreadyDecided,
            };
            throw new AnipError(type, "approve_request_and_store_grant: " + result.Reason);
        }

        // Emit approval_grant_issued audit event linking request <-> grant <-> approver.
        try
        {
            var approverSubject = approver.TryGetValue("subject", out var asObj) ? asObj as string : null;
            var approverRoot = approver.TryGetValue("root_principal", out var arObj) ? arObj as string : null;
            var entry = new AuditEntry
            {
                Capability = request.Capability,
                Issuer = _serviceId,
                Subject = approverSubject,
                RootPrincipal = approverRoot ?? approverSubject,
                Success = true,
                ResultSummary = new Dictionary<string, object>
                {
                    ["approver"] = approver,
                    ["requester"] = request.Requester,
                    ["grant_type"] = grantType,
                    ["scope"] = request.Scope,
                },
                ApprovalRequestId = approvalRequestId,
                ApprovalGrantId = grant.GrantId,
                EntryType = "approval_grant_issued",
                EventClass = "high_risk_success",
                RetentionTier = "long",
            };
            try
            {
                AuditLog.AppendAudit(_keys!, _storage!, entry);
            }
            catch
            {
                // best effort
            }
        }
        catch
        {
            // best effort
        }

        return grant;
    }

    // --- Discovery ---

    /// <summary>
    /// Builds the full discovery document per SPEC section 6.1.
    /// </summary>
    public Dictionary<string, object?> GetDiscovery(string? baseUrl)
    {
        var capsSummary = new Dictionary<string, object?>();
        foreach (var (name, cap) in _capabilities)
        {
            var decl = cap.Declaration;
            var sideEffectType = decl.SideEffect?.Type ?? "";
            var financial = decl.Cost?.Financial != null;

            capsSummary[name] = new Dictionary<string, object?>
            {
                ["description"] = decl.Description,
                ["side_effect"] = sideEffectType,
                ["minimum_scope"] = decl.MinimumScope,
                ["financial"] = financial,
                ["contract"] = decl.ContractVersion,
            };
        }

        var doc = new Dictionary<string, object?>
        {
            ["protocol"] = Constants.ProtocolVersion,
            ["compliance"] = "anip-compliant",
            ["profile"] = Constants.DefaultProfile,
            ["auth"] = new Dictionary<string, object?>
            {
                ["delegation_token_required"] = true,
                ["supported_formats"] = new List<string> { "anip-v1" },
                ["minimum_scope_for_discovery"] = "none",
            },
            ["capabilities"] = capsSummary,
            ["trust_level"] = _trustLevel,
        };

        var failureDisc = new Dictionary<string, object?>
        {
            ["detail_level"] = _disclosureLevel,
        };
        if (_disclosureLevel == "policy" && _disclosurePolicy != null)
        {
            failureDisc["caller_classes"] = _disclosurePolicy.Keys.ToList();
        }

        doc["posture"] = new Dictionary<string, object?>
        {
            ["audit"] = new Dictionary<string, object?>
            {
                ["retention"] = _retentionPolicy.DefaultRetention(),
                ["retention_enforced"] = _retentionRunning,
            },
            ["failure_disclosure"] = failureDisc,
            ["anchoring"] = new Dictionary<string, object?>
            {
                ["enabled"] = false,
                ["proofs_available"] = false,
            },
        };

        doc["endpoints"] = new Dictionary<string, object?>
        {
            ["manifest"] = "/anip/manifest",
            ["permissions"] = "/anip/permissions",
            ["invoke"] = "/anip/invoke/{capability}",
            ["tokens"] = "/anip/tokens",
            ["audit"] = "/anip/audit",
            ["checkpoints"] = "/anip/checkpoints",
            ["graph"] = "/anip/graph/{capability}",
            ["jwks"] = "/.well-known/jwks.json",
            // v0.23 SPEC §4.9: signed grant issuance endpoint.
            ["approval_grants"] = "/anip/approval_grants",
        };

        if (!string.IsNullOrEmpty(baseUrl))
        {
            doc["base_url"] = baseUrl;
        }

        return new Dictionary<string, object?>
        {
            ["anip_discovery"] = doc,
        };
    }

    /// <summary>
    /// Returns the full capability manifest.
    /// </summary>
    public AnipManifest GetManifest()
    {
        var caps = new Dictionary<string, CapabilityDeclaration>();
        foreach (var (name, cap) in _capabilities)
        {
            caps[name] = cap.Declaration;
        }

        return new AnipManifest
        {
            Protocol = Constants.ProtocolVersion,
            Profile = new ProfileVersions
            {
                Core = "1.0",
                Cost = "1.0",
                CapabilityGraph = "1.0",
                StateSession = "1.0",
                Observability = "1.0",
            },
            Capabilities = caps,
            Trust = new TrustPosture { Level = _trustLevel },
            ServiceIdentity = new ServiceIdentity
            {
                Id = _serviceId,
                JwksUri = "/.well-known/jwks.json",
                IssuerMode = "first-party",
            },
        };
    }

    /// <summary>
    /// Returns the manifest as canonical JSON bytes and its detached JWS signature.
    /// </summary>
    public SignedManifest GetSignedManifest()
    {
        var manifest = GetManifest();

        var data = JsonSerializer.Serialize(manifest, s_serializerOptions);
        var map = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(data)!;
        var bodyBytes = JsonSerializer.SerializeToUtf8Bytes(map);

        var signature = JwsSigner.SignDetached(_keys!.GetSigningKey(), _keys!.GetSigningKid(), bodyBytes);

        return new SignedManifest(bodyBytes, signature);
    }

    /// <summary>
    /// Returns the JWKS document for this service.
    /// </summary>
    public Dictionary<string, object> GetJwks()
    {
        return JwksSerializer.ToJwks(_keys!);
    }

    /// <summary>
    /// Returns a single capability declaration by name, or null if not found.
    /// </summary>
    public CapabilityDeclaration? GetCapabilityDeclaration(string name)
    {
        return _capabilities.TryGetValue(name, out var cap) ? cap.Declaration : null;
    }

    /// <summary>
    /// Returns the graph relationships (requires, composes_with) for a capability.
    /// Returns null if the capability does not exist.
    /// </summary>
    public Dictionary<string, object?>? GetCapabilityGraph(string name)
    {
        if (!_capabilities.TryGetValue(name, out var cap)) return null;
        var decl = cap.Declaration;
        return new Dictionary<string, object?>
        {
            ["capability"] = name,
            ["requires"] = decl.Requires ?? new List<CapabilityRequirement>(),
            ["composes_with"] = decl.ComposesWith ?? new List<CapabilityComposition>(),
        };
    }

    // --- Invocation ---

    /// <summary>
    /// Routes a capability invocation through validation, handler execution, and audit.
    /// </summary>
    public Dictionary<string, object?> Invoke(
        string capName,
        DelegationToken token,
        Dictionary<string, object?> parameters,
        InvokeOpts opts)
    {
        var invocationId = Constants.GenerateInvocationId();
        var invokeStart = DateTime.UtcNow;
        var invokeSuccess = false;

        try
        {
            // task_id precedence: token purpose.task_id is authoritative
            var tokenTaskId = !string.IsNullOrEmpty(token.Purpose?.TaskId) ? token.Purpose.TaskId : null;
            if (tokenTaskId != null && opts.TaskId != null && opts.TaskId != tokenTaskId)
            {
                return new Dictionary<string, object?>
                {
                    ["success"] = false,
                    ["failure"] = new Dictionary<string, object?>
                    {
                        ["type"] = Constants.FailurePurposeMismatch,
                        ["detail"] = $"Request task_id '{opts.TaskId}' does not match token purpose task_id '{tokenTaskId}'",
                        ["resolution"] = new Dictionary<string, object?> { ["action"] = "revalidate_state", ["recovery_class"] = Constants.RecoveryClassForAction("revalidate_state"), ["requires"] = "matching task_id or omit from request" },
                        ["retry"] = false,
                    },
                    ["invocation_id"] = invocationId,
                    ["client_reference_id"] = opts.ClientReferenceId,
                    ["task_id"] = opts.TaskId,
                    ["parent_invocation_id"] = opts.ParentInvocationId,
                    ["upstream_service"] = opts.UpstreamService,
                };
            }
            var effectiveTaskId = opts.TaskId ?? tokenTaskId;

            // 1. Look up capability.
            if (!_capabilities.TryGetValue(capName, out var capDef))
            {
                var failure = new Dictionary<string, object?>
                {
                    ["type"] = Constants.FailureUnknownCapability,
                    ["detail"] = $"Capability '{capName}' not found",
                    ["resolution"] = new Dictionary<string, object?>
                    {
                        ["action"] = "check_manifest",
                        ["recovery_class"] = Constants.RecoveryClassForAction("check_manifest"),
                    },
                };

                var effectiveLevel = DisclosureControl.Resolve(_disclosureLevel, null, _disclosurePolicy);
                failure = FailureRedaction.Redact(failure, effectiveLevel);

                return new Dictionary<string, object?>
                {
                    ["success"] = false,
                    ["failure"] = failure,
                    ["invocation_id"] = invocationId,
                    ["client_reference_id"] = opts.ClientReferenceId,
                    ["task_id"] = effectiveTaskId,
                    ["parent_invocation_id"] = opts.ParentInvocationId,
                    ["upstream_service"] = opts.UpstreamService,
                };
            }

            // Fire OnInvokeStart hook.
            if (_hooks?.OnInvokeStart != null)
            {
                ObservabilityHooks.CallHook(() => _hooks.OnInvokeStart(invocationId, capName, token.Subject));
            }

            // 2. Check streaming support.
            if (opts.Stream)
            {
                var supportsStreaming = capDef.Declaration.ResponseModes?.Contains("streaming") == true;
                string streamFailDetail;
                if (!supportsStreaming)
                {
                    streamFailDetail = $"Capability '{capName}' does not support streaming";
                }
                else
                {
                    streamFailDetail = "Use InvokeStream for streaming invocations";
                }

                var streamFailure = new Dictionary<string, object?>
                {
                    ["type"] = Constants.FailureStreamingNotSupported,
                    ["detail"] = streamFailDetail,
                };

                var effectiveLevelStream = DisclosureControl.Resolve(_disclosureLevel, null, _disclosurePolicy);
                streamFailure = FailureRedaction.Redact(streamFailure, effectiveLevelStream);

                return new Dictionary<string, object?>
                {
                    ["success"] = false,
                    ["failure"] = streamFailure,
                    ["invocation_id"] = invocationId,
                    ["client_reference_id"] = opts.ClientReferenceId,
                    ["task_id"] = effectiveTaskId,
                    ["parent_invocation_id"] = opts.ParentInvocationId,
                    ["upstream_service"] = opts.UpstreamService,
                };
            }

            // 3. Validate token scope.
            try
            {
                DelegationEngine.ValidateScope(token, capDef.Declaration.MinimumScope);
            }
            catch (AnipError anipErr)
            {
                // Fire scope validation hook (denied).
                if (_hooks?.OnScopeValidation != null)
                {
                    ObservabilityHooks.CallHook(() => _hooks.OnScopeValidation(capName, false));
                }

                var failure = new Dictionary<string, object?>
                {
                    ["type"] = anipErr.ErrorType,
                    ["detail"] = anipErr.Detail,
                };
                if (anipErr.Resolution != null)
                {
                    failure["resolution"] = new Dictionary<string, object?>
                    {
                        ["action"] = anipErr.Resolution.Action,
                        ["recovery_class"] = !string.IsNullOrEmpty(anipErr.Resolution.RecoveryClass)
                            ? anipErr.Resolution.RecoveryClass
                            : Constants.RecoveryClassForAction(anipErr.Resolution.Action),
                    };
                }

                // Log audit for scope failure.
                AppendAuditEntry(capName, token, false, anipErr.ErrorType, null, null,
                    invocationId, opts.ClientReferenceId, effectiveTaskId, opts.ParentInvocationId,
                    opts.UpstreamService,
                    capDef.Declaration.SideEffect?.Type);

                // Apply failure redaction.
                var effectiveLevel = DisclosureControl.Resolve(_disclosureLevel, TokenClaimsMap(token), _disclosurePolicy);
                failure = FailureRedaction.Redact(failure, effectiveLevel);

                return new Dictionary<string, object?>
                {
                    ["success"] = false,
                    ["failure"] = failure,
                    ["invocation_id"] = invocationId,
                    ["client_reference_id"] = opts.ClientReferenceId,
                    ["task_id"] = effectiveTaskId,
                    ["parent_invocation_id"] = opts.ParentInvocationId,
                    ["upstream_service"] = opts.UpstreamService,
                };
            }

            // Fire scope validation hook (granted).
            if (_hooks?.OnScopeValidation != null)
            {
                ObservabilityHooks.CallHook(() => _hooks.OnScopeValidation(capName, true));
            }

            // --- Budget, binding, and control requirement enforcement (v0.14) ---

            // Parse invocation-level budget hint.
            Budget? requestBudget = opts.Budget;

            // Determine effective budget (token is ceiling, invocation hint can only narrow).
            Budget? effectiveBudget = null;
            if (token.Constraints.Budget != null)
            {
                effectiveBudget = token.Constraints.Budget;
                if (requestBudget != null)
                {
                    if (requestBudget.Currency != effectiveBudget.Currency)
                    {
                        var failure = new Dictionary<string, object?>
                        {
                            ["type"] = Constants.FailureBudgetCurrencyMismatch,
                            ["detail"] = $"Invocation budget is in {requestBudget.Currency} but token budget is in {effectiveBudget.Currency}",
                        };
                        var effectiveLevel = DisclosureControl.Resolve(_disclosureLevel, TokenClaimsMap(token), _disclosurePolicy);
                        failure = FailureRedaction.Redact(failure, effectiveLevel);
                        return new Dictionary<string, object?>
                        {
                            ["success"] = false,
                            ["failure"] = failure,
                            ["invocation_id"] = invocationId,
                            ["client_reference_id"] = opts.ClientReferenceId,
                            ["task_id"] = effectiveTaskId,
                            ["parent_invocation_id"] = opts.ParentInvocationId,
                            ["upstream_service"] = opts.UpstreamService,
                        };
                    }
                    var narrowedAmount = effectiveBudget.MaxAmount;
                    if (requestBudget.MaxAmount < narrowedAmount)
                    {
                        narrowedAmount = requestBudget.MaxAmount;
                    }
                    effectiveBudget = new Budget
                    {
                        Currency = effectiveBudget.Currency,
                        MaxAmount = narrowedAmount,
                    };
                }
            }
            else if (requestBudget != null)
            {
                effectiveBudget = requestBudget;
            }

            // Budget enforcement against declared cost.
            double? checkAmount = null;
            if (effectiveBudget != null)
            {
                var decl = capDef.Declaration;
                if (decl.Cost != null && decl.Cost.Financial != null)
                {
                    if (decl.Cost.Financial.Currency != effectiveBudget.Currency)
                    {
                        var failure = new Dictionary<string, object?>
                        {
                            ["type"] = Constants.FailureBudgetCurrencyMismatch,
                            ["detail"] = $"Token budget is in {effectiveBudget.Currency} but capability cost is in {decl.Cost.Financial.Currency}",
                        };
                        var effectiveLevel = DisclosureControl.Resolve(_disclosureLevel, TokenClaimsMap(token), _disclosurePolicy);
                        failure = FailureRedaction.Redact(failure, effectiveLevel);
                        return new Dictionary<string, object?>
                        {
                            ["success"] = false,
                            ["failure"] = failure,
                            ["invocation_id"] = invocationId,
                            ["client_reference_id"] = opts.ClientReferenceId,
                            ["task_id"] = effectiveTaskId,
                            ["parent_invocation_id"] = opts.ParentInvocationId,
                            ["upstream_service"] = opts.UpstreamService,
                        };
                    }

                    switch (decl.Cost.Certainty)
                    {
                        case "fixed":
                            checkAmount = decl.Cost.Financial.Amount;
                            break;
                        case "estimated":
                            if (decl.RequiresBinding != null && decl.RequiresBinding.Count > 0)
                            {
                                checkAmount = ResolveBoundPrice(decl.RequiresBinding, parameters);
                            }
                            else
                            {
                                var failure = new Dictionary<string, object?>
                                {
                                    ["type"] = Constants.FailureBudgetNotEnforceable,
                                    ["detail"] = $"Capability {capName} has estimated cost but no requires_binding — budget cannot be enforced",
                                };
                                var effectiveLevel = DisclosureControl.Resolve(_disclosureLevel, TokenClaimsMap(token), _disclosurePolicy);
                                failure = FailureRedaction.Redact(failure, effectiveLevel);
                                return new Dictionary<string, object?>
                                {
                                    ["success"] = false,
                                    ["failure"] = failure,
                                    ["invocation_id"] = invocationId,
                                    ["client_reference_id"] = opts.ClientReferenceId,
                                    ["task_id"] = effectiveTaskId,
                                    ["parent_invocation_id"] = opts.ParentInvocationId,
                                    ["upstream_service"] = opts.UpstreamService,
                                };
                            }
                            break;
                        case "dynamic":
                            checkAmount = decl.Cost.Financial.UpperBound;
                            break;
                    }

                    if (checkAmount != null && checkAmount.Value > effectiveBudget.MaxAmount)
                    {
                        var failure = new Dictionary<string, object?>
                        {
                            ["type"] = Constants.FailureBudgetExceeded,
                            ["detail"] = $"Cost ${checkAmount.Value} exceeds budget ${effectiveBudget.MaxAmount}",
                        };
                        var effectiveLevel = DisclosureControl.Resolve(_disclosureLevel, TokenClaimsMap(token), _disclosurePolicy);
                        failure = FailureRedaction.Redact(failure, effectiveLevel);
                        return new Dictionary<string, object?>
                        {
                            ["success"] = false,
                            ["failure"] = failure,
                            ["invocation_id"] = invocationId,
                            ["client_reference_id"] = opts.ClientReferenceId,
                            ["task_id"] = effectiveTaskId,
                            ["parent_invocation_id"] = opts.ParentInvocationId,
                            ["upstream_service"] = opts.UpstreamService,
                            ["budget_context"] = new Dictionary<string, object?>
                            {
                                ["budget_max"] = effectiveBudget.MaxAmount,
                                ["budget_currency"] = effectiveBudget.Currency,
                                ["cost_check_amount"] = checkAmount.Value,
                                ["cost_certainty"] = decl.Cost.Certainty,
                            },
                        };
                    }
                }
            }

            // Binding enforcement.
            if (capDef.Declaration.RequiresBinding != null)
            {
                foreach (var binding in capDef.Declaration.RequiresBinding)
                {
                    var hasVal = parameters.TryGetValue(binding.Field, out var val) && val != null;
                    if (!hasVal)
                    {
                        var sourceDesc = !string.IsNullOrEmpty(binding.SourceCapability)
                            ? binding.SourceCapability
                            : "source capability";
                        var failure = new Dictionary<string, object?>
                        {
                            ["type"] = Constants.FailureBindingMissing,
                            ["detail"] = $"Capability {capName} requires '{binding.Field}' (type: {binding.Type})",
                            ["resolution"] = new Dictionary<string, object?>
                            {
                                ["action"] = "obtain_binding",
                                ["recovery_class"] = Constants.RecoveryClassForAction("obtain_binding"),
                                ["requires"] = $"invoke {sourceDesc} to obtain a {binding.Field}",
                            },
                        };
                        var effectiveLevel = DisclosureControl.Resolve(_disclosureLevel, TokenClaimsMap(token), _disclosurePolicy);
                        failure = FailureRedaction.Redact(failure, effectiveLevel);
                        return new Dictionary<string, object?>
                        {
                            ["success"] = false,
                            ["failure"] = failure,
                            ["invocation_id"] = invocationId,
                            ["client_reference_id"] = opts.ClientReferenceId,
                            ["task_id"] = effectiveTaskId,
                            ["parent_invocation_id"] = opts.ParentInvocationId,
                            ["upstream_service"] = opts.UpstreamService,
                        };
                    }

                    if (!string.IsNullOrEmpty(binding.MaxAge))
                    {
                        var age = ResolveBindingAge(val!);
                        if (age >= TimeSpan.Zero)
                        {
                            var maxAge = ParseISO8601Duration(binding.MaxAge);
                            if (maxAge > TimeSpan.Zero && age > maxAge)
                            {
                                var sourceDesc = !string.IsNullOrEmpty(binding.SourceCapability)
                                    ? binding.SourceCapability
                                    : "source capability";
                                var failure = new Dictionary<string, object?>
                                {
                                    ["type"] = Constants.FailureBindingStale,
                                    ["detail"] = $"Binding '{binding.Field}' has exceeded max_age of {binding.MaxAge}",
                                    ["resolution"] = new Dictionary<string, object?>
                                    {
                                        ["action"] = "refresh_binding",
                                        ["recovery_class"] = Constants.RecoveryClassForAction("refresh_binding"),
                                        ["requires"] = $"invoke {sourceDesc} again for a fresh {binding.Field}",
                                    },
                                };
                                var effectiveLevel = DisclosureControl.Resolve(_disclosureLevel, TokenClaimsMap(token), _disclosurePolicy);
                                failure = FailureRedaction.Redact(failure, effectiveLevel);
                                return new Dictionary<string, object?>
                                {
                                    ["success"] = false,
                                    ["failure"] = failure,
                                    ["invocation_id"] = invocationId,
                                    ["client_reference_id"] = opts.ClientReferenceId,
                                    ["task_id"] = effectiveTaskId,
                                    ["parent_invocation_id"] = opts.ParentInvocationId,
                                    ["upstream_service"] = opts.UpstreamService,
                                };
                            }
                        }
                    }
                }
            }

            // Control requirement enforcement (reject only — no warn in v0.14).
            if (capDef.Declaration.ControlRequirements != null)
            {
                foreach (var req in capDef.Declaration.ControlRequirements)
                {
                    var satisfied = true;
                    switch (req.Type)
                    {
                        case "cost_ceiling":
                            satisfied = effectiveBudget != null;
                            break;
                        case "stronger_delegation_required":
                            satisfied = token.Purpose?.Capability == capName;
                            break;
                    }

                    if (!satisfied)
                    {
                        var failure = new Dictionary<string, object?>
                        {
                            ["type"] = Constants.FailureControlRequirementUnsatisfied,
                            ["detail"] = $"Capability {capName} requires {req.Type}",
                            ["unsatisfied_requirements"] = new List<string> { req.Type },
                        };
                        var effectiveLevel = DisclosureControl.Resolve(_disclosureLevel, TokenClaimsMap(token), _disclosurePolicy);
                        failure = FailureRedaction.Redact(failure, effectiveLevel);
                        return new Dictionary<string, object?>
                        {
                            ["success"] = false,
                            ["failure"] = failure,
                            ["invocation_id"] = invocationId,
                            ["client_reference_id"] = opts.ClientReferenceId,
                            ["task_id"] = effectiveTaskId,
                            ["parent_invocation_id"] = opts.ParentInvocationId,
                            ["upstream_service"] = opts.UpstreamService,
                        };
                    }
                }
            }

            // 4. Build invocation context.
            var rootPrincipal = token.RootPrincipal ?? token.Issuer;

            var ctx = new InvocationContext(
                token: token,
                rootPrincipal: rootPrincipal,
                subject: token.Subject,
                scopes: token.Scope,
                delegationChain: new List<string> { token.TokenId },
                invocationId: invocationId,
                clientReferenceId: opts.ClientReferenceId,
                taskId: effectiveTaskId,
                parentInvocationId: opts.ParentInvocationId,
                emitProgress: _ => false, // No-op for unary invocations.
                upstreamService: opts.UpstreamService
            );

            // 4b. v0.23 §4.8 Phase A+B: validate + atomically reserve any
            // continuation approval_grant before the handler runs. session_id
            // is taken from the signed delegation token only (never from input).
            var approvalGrantId = opts.ApprovalGrant;
            if (!string.IsNullOrEmpty(approvalGrantId))
            {
                try
                {
                    var cv = V023.ValidateContinuationGrant(
                        _storage!, _keys!, approvalGrantId, capName, parameters,
                        token.Scope, token.SessionId, V023.UtcNowIso());
                    if (cv.FailureType != null)
                    {
                        throw new AnipError(cv.FailureType,
                            "approval_grant validation failed: " + cv.FailureType);
                    }
                    var res = _storage!.TryReserveGrant(approvalGrantId, V023.UtcNowIso());
                    if (!res.Ok)
                    {
                        var type = res.Reason switch
                        {
                            "grant_consumed" => Constants.FailureGrantConsumed,
                            "grant_expired" => Constants.FailureGrantExpired,
                            _ => Constants.FailureGrantNotFound,
                        };
                        throw new AnipError(type, "approval_grant reservation failed: " + res.Reason);
                    }
                }
                catch (AnipError ae)
                {
                    AppendAuditEntry(capName, token, false, ae.ErrorType,
                        new Dictionary<string, object?> { ["detail"] = ae.Detail }, null,
                        invocationId, opts.ClientReferenceId, effectiveTaskId, opts.ParentInvocationId,
                        opts.UpstreamService, capDef.Declaration.SideEffect?.Type,
                        approvalGrantId: approvalGrantId);
                    var failureA = new Dictionary<string, object?>
                    {
                        ["type"] = ae.ErrorType,
                        ["detail"] = ae.Detail,
                    };
                    var levelA = DisclosureControl.Resolve(_disclosureLevel, TokenClaimsMap(token), _disclosurePolicy);
                    failureA = FailureRedaction.Redact(failureA, levelA);
                    return new Dictionary<string, object?>
                    {
                        ["success"] = false,
                        ["failure"] = failureA,
                        ["invocation_id"] = invocationId,
                        ["client_reference_id"] = opts.ClientReferenceId,
                        ["task_id"] = effectiveTaskId,
                        ["parent_invocation_id"] = opts.ParentInvocationId,
                        ["upstream_service"] = opts.UpstreamService,
                    };
                }
                catch (Exception)
                {
                    AppendAuditEntry(capName, token, false, Constants.FailureUnavailable, null, null,
                        invocationId, opts.ClientReferenceId, effectiveTaskId, opts.ParentInvocationId,
                        opts.UpstreamService, capDef.Declaration.SideEffect?.Type,
                        approvalGrantId: approvalGrantId);
                    return new Dictionary<string, object?>
                    {
                        ["success"] = false,
                        ["failure"] = new Dictionary<string, object?>
                        {
                            ["type"] = Constants.FailureUnavailable,
                            ["detail"] = "approval grant validation unavailable",
                        },
                        ["invocation_id"] = invocationId,
                        ["client_reference_id"] = opts.ClientReferenceId,
                        ["task_id"] = effectiveTaskId,
                        ["parent_invocation_id"] = opts.ParentInvocationId,
                        ["upstream_service"] = opts.UpstreamService,
                    };
                }
            }

            // 5. Call handler. Composed capabilities run V023.ExecuteComposition
            // instead of the registered handler — each child step re-enters
            // Invoke() with the same token, parent_invocation_id lineage.
            Dictionary<string, object?> result;
            try
            {
                if (capDef.Declaration.Kind == "composed")
                {
                    var childToken = token;
                    var parentInvocationIdInner = invocationId;
                    var clientRefIdInner = opts.ClientReferenceId;
                    var upstreamInner = opts.UpstreamService;
                    var taskIdInner = effectiveTaskId;
                    V023.InvokeStepFunc invokeStep = (childCap, childParams) =>
                    {
                        var childOpts = new InvokeOpts
                        {
                            ClientReferenceId = clientRefIdInner,
                            TaskId = taskIdInner,
                            ParentInvocationId = parentInvocationIdInner,
                            UpstreamService = upstreamInner,
                            Stream = false,
                        };
                        return Invoke(childCap, childToken, childParams, childOpts);
                    };
                    result = V023.ExecuteComposition(capName, capDef.Declaration, parameters, invokeStep);
                }
                else
                {
                    result = capDef.Handler(ctx, parameters);
                }
            }
            catch (AnipError anipErr)
            {
                // v0.23: materialize the ApprovalRequest BEFORE the audit log
                // so audit entries can carry approval_request_id. SPEC.md §4.7
                // persistence invariant: storage failure → service_unavailable.
                ApprovalRequiredMetadata? materialized = null;
                var approvalPersistFailed = false;
                string? approvalPersistErr = null;
                var effectiveErrorType = anipErr.ErrorType;
                if (anipErr.ErrorType == Constants.FailureApprovalRequired)
                {
                    try
                    {
                        if (anipErr.ApprovalRequired != null
                            && !string.IsNullOrEmpty(anipErr.ApprovalRequired.ApprovalRequestId))
                        {
                            materialized = anipErr.ApprovalRequired;
                        }
                        else
                        {
                            var requesterMap = new Dictionary<string, object>
                            {
                                ["subject"] = token.Subject,
                                ["root_principal"] = token.RootPrincipal ?? token.Issuer,
                            };
                            var paramsMap = parameters.ToDictionary(
                                kv => kv.Key,
                                kv => (object)(kv.Value ?? string.Empty));
                            var mat = V023.MaterializeApprovalRequest(
                                _storage!, capDef.Declaration, invocationId,
                                requesterMap, paramsMap, new Dictionary<string, object>(),
                                null);
                            materialized = mat.Metadata;
                        }
                    }
                    catch (Exception ape)
                    {
                        approvalPersistFailed = true;
                        approvalPersistErr = ape.Message;
                        effectiveErrorType = Constants.FailureUnavailable;
                    }
                }

                var approvalRequestIdAudit = (materialized != null && !approvalPersistFailed)
                    ? materialized.ApprovalRequestId
                    : null;

                AppendAuditEntry(capName, token, false, effectiveErrorType,
                    new Dictionary<string, object?> { ["detail"] = anipErr.Detail }, null,
                    invocationId, opts.ClientReferenceId, effectiveTaskId, opts.ParentInvocationId,
                    opts.UpstreamService,
                    capDef.Declaration.SideEffect?.Type,
                    approvalRequestId: approvalRequestIdAudit,
                    approvalGrantId: approvalGrantId);

                // v0.23: emit a dedicated approval_request_created event
                // linking the original invocation to the approval request.
                if (approvalRequestIdAudit != null)
                {
                    try
                    {
                        AppendAuditEntry(capName, token, true, null, null, null,
                            string.Empty, null, effectiveTaskId, invocationId,
                            null, capDef.Declaration.SideEffect?.Type,
                            approvalRequestId: approvalRequestIdAudit,
                            entryType: "approval_request_created");
                    }
                    catch
                    {
                        // best effort
                    }
                }

                var failure = new Dictionary<string, object?>
                {
                    ["type"] = effectiveErrorType,
                    ["detail"] = approvalPersistFailed
                        ? "approval flow unavailable: " + approvalPersistErr
                        : anipErr.Detail,
                };
                if (anipErr.Resolution != null && !approvalPersistFailed)
                {
                    failure["resolution"] = new Dictionary<string, object?>
                    {
                        ["action"] = anipErr.Resolution.Action,
                        ["recovery_class"] = !string.IsNullOrEmpty(anipErr.Resolution.RecoveryClass)
                            ? anipErr.Resolution.RecoveryClass
                            : Constants.RecoveryClassForAction(anipErr.Resolution.Action),
                    };
                }
                if (approvalPersistFailed)
                {
                    failure["resolution"] = new Dictionary<string, object?>
                    {
                        ["action"] = "wait_and_retry",
                        ["recovery_class"] = "wait_then_retry",
                    };
                }
                else if (materialized != null)
                {
                    var apReq = new Dictionary<string, object?>
                    {
                        ["approval_request_id"] = materialized.ApprovalRequestId,
                        ["preview_digest"] = materialized.PreviewDigest,
                        ["requested_parameters_digest"] = materialized.RequestedParametersDigest,
                    };
                    if (materialized.GrantPolicy != null)
                    {
                        apReq["grant_policy"] = materialized.GrantPolicy;
                    }
                    failure["approval_required"] = apReq;
                }

                var effectiveLevelErr = DisclosureControl.Resolve(_disclosureLevel, TokenClaimsMap(token), _disclosurePolicy);
                failure = FailureRedaction.Redact(failure, effectiveLevelErr);

                return new Dictionary<string, object?>
                {
                    ["success"] = false,
                    ["failure"] = failure,
                    ["invocation_id"] = invocationId,
                    ["client_reference_id"] = opts.ClientReferenceId,
                    ["task_id"] = effectiveTaskId,
                    ["parent_invocation_id"] = opts.ParentInvocationId,
                    ["upstream_service"] = opts.UpstreamService,
                };
            }
            catch (Exception)
            {
                AppendAuditEntry(capName, token, false, Constants.FailureInternalError, null, null,
                    invocationId, opts.ClientReferenceId, effectiveTaskId, opts.ParentInvocationId,
                    opts.UpstreamService,
                    capDef.Declaration.SideEffect?.Type);

                var failure = new Dictionary<string, object?>
                {
                    ["type"] = Constants.FailureInternalError,
                    ["detail"] = "Internal error",
                };

                var effectiveLevelExc = DisclosureControl.Resolve(_disclosureLevel, TokenClaimsMap(token), _disclosurePolicy);
                failure = FailureRedaction.Redact(failure, effectiveLevelExc);

                return new Dictionary<string, object?>
                {
                    ["success"] = false,
                    ["failure"] = failure,
                    ["invocation_id"] = invocationId,
                    ["client_reference_id"] = opts.ClientReferenceId,
                    ["task_id"] = effectiveTaskId,
                    ["parent_invocation_id"] = opts.ParentInvocationId,
                    ["upstream_service"] = opts.UpstreamService,
                };
            }

            // 6. Extract cost actual from context.
            var costActual = ctx.CostActual;

            // 7. Log audit (success). Continuation success entries reference
            // the consumed grant per SPEC §4.9 step 11.
            AppendAuditEntry(capName, token, true, null, result, costActual,
                invocationId, opts.ClientReferenceId, effectiveTaskId, opts.ParentInvocationId,
                opts.UpstreamService,
                capDef.Declaration.SideEffect?.Type,
                approvalGrantId: approvalGrantId);

            // 8. Build response.
            var resp = new Dictionary<string, object?>
            {
                ["success"] = true,
                ["result"] = result,
                ["invocation_id"] = invocationId,
                ["client_reference_id"] = opts.ClientReferenceId,
                ["task_id"] = effectiveTaskId,
                ["parent_invocation_id"] = opts.ParentInvocationId,
                ["upstream_service"] = opts.UpstreamService,
            };
            if (costActual != null)
            {
                resp["cost_actual"] = costActual;
            }

            // Budget context in response (v0.14).
            if (effectiveBudget != null)
            {
                double? costActualAmount = costActual?.Financial?.Amount;

                string? costCertainty = null;
                if (capDef.Declaration.Cost != null)
                {
                    costCertainty = capDef.Declaration.Cost.Certainty;
                }

                var budgetCtx = new Dictionary<string, object?>
                {
                    ["budget_max"] = effectiveBudget.MaxAmount,
                    ["budget_currency"] = effectiveBudget.Currency,
                    ["cost_certainty"] = costCertainty,
                    ["within_budget"] = true,
                };
                if (checkAmount != null)
                {
                    budgetCtx["cost_check_amount"] = checkAmount.Value;
                }
                if (costActualAmount != null)
                {
                    budgetCtx["cost_actual"] = costActualAmount.Value;
                }
                resp["budget_context"] = budgetCtx;
            }

            invokeSuccess = true;
            return resp;
        }
        finally
        {
            // Fire completion hooks on all exit paths.
            if (_hooks != null)
            {
                var durationMs = (long)(DateTime.UtcNow - invokeStart).TotalMilliseconds;
                if (_hooks.OnInvokeComplete != null)
                {
                    var success = invokeSuccess;
                    ObservabilityHooks.CallHook(() => _hooks.OnInvokeComplete(invocationId, capName, success, durationMs));
                }
                if (_hooks.OnInvokeDuration != null)
                {
                    var success = invokeSuccess;
                    ObservabilityHooks.CallHook(() => _hooks.OnInvokeDuration(capName, durationMs, success));
                }
            }
        }
    }

    /// <summary>
    /// Routes a streaming capability invocation.
    /// Returns a StreamResult whose Events channel emits progress events
    /// followed by exactly one terminal event (completed or failed), then closes.
    /// </summary>
    public StreamResult InvokeStream(
        string capName,
        DelegationToken token,
        Dictionary<string, object?> parameters,
        InvokeOpts opts)
    {
        var invocationId = Constants.GenerateInvocationId();

        // task_id precedence: token purpose.task_id is authoritative
        var tokenTaskId = !string.IsNullOrEmpty(token.Purpose?.TaskId) ? token.Purpose.TaskId : null;
        if (tokenTaskId != null && opts.TaskId != null && opts.TaskId != tokenTaskId)
        {
            throw new AnipError(Constants.FailurePurposeMismatch,
                $"Request task_id '{opts.TaskId}' does not match token purpose task_id '{tokenTaskId}'");
        }
        var effectiveTaskId = opts.TaskId ?? tokenTaskId;

        // 1. Look up capability.
        if (!_capabilities.TryGetValue(capName, out var capDef))
        {
            throw new AnipError(Constants.FailureUnknownCapability,
                $"Capability '{capName}' not found");
        }

        // 2. Check streaming support.
        if (capDef.Declaration.ResponseModes?.Contains("streaming") != true)
        {
            throw new AnipError(Constants.FailureStreamingNotSupported,
                $"Capability '{capName}' does not support streaming");
        }

        // 3. Validate token scope.
        DelegationEngine.ValidateScope(token, capDef.Declaration.MinimumScope);

        // 3b. v0.23 §4.8 Phase A+B: validate and atomically reserve the
        // approval_grant BEFORE any handler / event emission. Reservation is
        // the security boundary — once reserved, the grant is spent on this
        // attempt. Failures throw AnipError synchronously so the transport
        // adapter maps to a JSON 4xx and no SSE stream opens.
        var streamApprovalGrantId = opts.ApprovalGrant;
        if (!string.IsNullOrEmpty(streamApprovalGrantId))
        {
            try
            {
                var cv = V023.ValidateContinuationGrant(
                    _storage!, _keys!, streamApprovalGrantId, capName, parameters,
                    token.Scope, token.SessionId, V023.UtcNowIso());
                if (cv.FailureType != null)
                {
                    throw new AnipError(cv.FailureType,
                        "approval_grant validation failed: " + cv.FailureType);
                }
                var res = _storage!.TryReserveGrant(streamApprovalGrantId, V023.UtcNowIso());
                if (!res.Ok)
                {
                    var type = res.Reason switch
                    {
                        "grant_consumed" => Constants.FailureGrantConsumed,
                        "grant_expired" => Constants.FailureGrantExpired,
                        _ => Constants.FailureGrantNotFound,
                    };
                    throw new AnipError(type, "approval_grant reservation failed: " + res.Reason);
                }
            }
            catch (AnipError)
            {
                throw;
            }
            catch (Exception ex)
            {
                throw new AnipError(Constants.FailureInternalError,
                    "grant reservation failed: " + ex.Message);
            }
        }
        var reservedGrantId = streamApprovalGrantId;

        // 4. Build invocation context with streaming EmitProgress.
        var rootPrincipal = token.RootPrincipal ?? token.Issuer;
        var channel = Channel.CreateBounded<StreamEvent>(16);
        var lockObj = new object();
        var closed = false;
        var clientRefId = opts.ClientReferenceId;
        var parentInvId = opts.ParentInvocationId;
        var upstreamSvc = opts.UpstreamService;

        Func<Dictionary<string, object?>, bool> emitProgress = payload =>
        {
            lock (lockObj)
            {
                if (closed) return false;
            }

            var evt = new StreamEvent
            {
                Type = "progress",
                Payload = new Dictionary<string, object?>
                {
                    ["invocation_id"] = invocationId,
                    ["client_reference_id"] = string.IsNullOrEmpty(clientRefId) ? null : clientRefId,
                    ["task_id"] = effectiveTaskId,
                    ["parent_invocation_id"] = parentInvId,
                    ["upstream_service"] = upstreamSvc,
                    ["timestamp"] = DateTime.UtcNow.ToString("o"),
                    ["payload"] = payload,
                },
            };

            return channel.Writer.TryWrite(evt);
        };

        var ctx = new InvocationContext(
            token: token,
            rootPrincipal: rootPrincipal,
            subject: token.Subject,
            scopes: token.Scope,
            delegationChain: new List<string> { token.TokenId },
            invocationId: invocationId,
            clientReferenceId: clientRefId,
            taskId: effectiveTaskId,
            parentInvocationId: parentInvId,
            emitProgress: emitProgress,
            upstreamService: upstreamSvc
        );

        // 5. Run handler in background task.
        _ = Task.Run(async () =>
        {
            try
            {
                Dictionary<string, object?> result;
                try
                {
                    result = capDef.Handler(ctx, parameters);
                }
                catch (AnipError anipErr)
                {
                    AppendAuditEntry(capName, token, false, anipErr.ErrorType,
                        new Dictionary<string, object?> { ["detail"] = anipErr.Detail }, null,
                        invocationId, clientRefId, effectiveTaskId, parentInvId,
                        upstreamSvc,
                        capDef.Declaration.SideEffect?.Type,
                        approvalGrantId: reservedGrantId);

                    var failureObj = new Dictionary<string, object?>
                    {
                        ["type"] = anipErr.ErrorType,
                        ["detail"] = anipErr.Detail,
                        ["retry"] = anipErr.Retry,
                        ["resolution"] = anipErr.Resolution != null
                            ? (object)anipErr.Resolution
                            : null,
                    };

                    var effectiveLevel = DisclosureControl.Resolve(_disclosureLevel, TokenClaimsMap(token), _disclosurePolicy);
                    failureObj = FailureRedaction.Redact(failureObj, effectiveLevel);

                    await channel.Writer.WriteAsync(new StreamEvent
                    {
                        Type = "failed",
                        Payload = new Dictionary<string, object?>
                        {
                            ["invocation_id"] = invocationId,
                            ["client_reference_id"] = string.IsNullOrEmpty(clientRefId) ? null : clientRefId,
                            ["task_id"] = effectiveTaskId,
                            ["parent_invocation_id"] = parentInvId,
                            ["upstream_service"] = upstreamSvc,
                            ["timestamp"] = DateTime.UtcNow.ToString("o"),
                            ["success"] = false,
                            ["failure"] = failureObj,
                        },
                    });
                    return;
                }
                catch (Exception)
                {
                    AppendAuditEntry(capName, token, false, Constants.FailureInternalError, null, null,
                        invocationId, clientRefId, effectiveTaskId, parentInvId,
                        upstreamSvc,
                        capDef.Declaration.SideEffect?.Type,
                        approvalGrantId: reservedGrantId);

                    var failureObj = new Dictionary<string, object?>
                    {
                        ["type"] = Constants.FailureInternalError,
                        ["detail"] = "Internal error",
                        ["resolution"] = null,
                        ["retry"] = false,
                    };

                    var effectiveLevel = DisclosureControl.Resolve(_disclosureLevel, TokenClaimsMap(token), _disclosurePolicy);
                    failureObj = FailureRedaction.Redact(failureObj, effectiveLevel);

                    await channel.Writer.WriteAsync(new StreamEvent
                    {
                        Type = "failed",
                        Payload = new Dictionary<string, object?>
                        {
                            ["invocation_id"] = invocationId,
                            ["client_reference_id"] = string.IsNullOrEmpty(clientRefId) ? null : clientRefId,
                            ["task_id"] = effectiveTaskId,
                            ["parent_invocation_id"] = parentInvId,
                            ["upstream_service"] = upstreamSvc,
                            ["timestamp"] = DateTime.UtcNow.ToString("o"),
                            ["success"] = false,
                            ["failure"] = failureObj,
                        },
                    });
                    return;
                }

                // Success
                var costActual = ctx.CostActual;
                AppendAuditEntry(capName, token, true, null, result, costActual,
                    invocationId, clientRefId, effectiveTaskId, parentInvId,
                    upstreamSvc,
                    capDef.Declaration.SideEffect?.Type,
                    approvalGrantId: reservedGrantId);

                var payload = new Dictionary<string, object?>
                {
                    ["invocation_id"] = invocationId,
                    ["client_reference_id"] = string.IsNullOrEmpty(clientRefId) ? null : clientRefId,
                    ["task_id"] = effectiveTaskId,
                    ["parent_invocation_id"] = parentInvId,
                    ["upstream_service"] = upstreamSvc,
                    ["timestamp"] = DateTime.UtcNow.ToString("o"),
                    ["success"] = true,
                    ["result"] = result,
                    ["cost_actual"] = costActual,
                };

                await channel.Writer.WriteAsync(new StreamEvent
                {
                    Type = "completed",
                    Payload = payload,
                });
            }
            finally
            {
                lock (lockObj)
                {
                    closed = true;
                }
                channel.Writer.Complete();
            }
        });

        return new StreamResult(
            channel.Reader,
            () =>
            {
                lock (lockObj) { closed = true; }
            }
        );
    }

    // --- Permissions ---

    /// <summary>
    /// Checks the token's scope against all registered capabilities
    /// and returns what the token can and cannot do.
    /// </summary>
    public PermissionResponse DiscoverPermissions(DelegationToken token)
    {
        var available = new List<AvailableCapability>();
        var restricted = new List<RestrictedCapability>();
        var denied = new List<DeniedCapability>();

        var tokenScopeEntries = token.Scope
            .Select(s => (Base: s.Split(':')[0], Full: s))
            .ToList();

        var rootPrincipal = token.RootPrincipal ?? token.Issuer;

        foreach (var (name, cap) in _capabilities)
        {
            var requiredScopes = cap.Declaration.MinimumScope;
            var matchedScopeStrs = new List<string>();
            var missing = new List<string>();

            foreach (var required in requiredScopes)
            {
                string? matchedFull = null;
                foreach (var entry in tokenScopeEntries)
                {
                    if (entry.Base == required || required.StartsWith(entry.Base + "."))
                    {
                        matchedFull = entry.Full;
                        break;
                    }
                }

                if (matchedFull != null)
                {
                    matchedScopeStrs.Add(matchedFull);
                }
                else
                {
                    missing.Add(required);
                }
            }

            if (missing.Count == 0)
            {
                // Scope matched — check token-evaluable control requirements.
                var unmet = new List<string>();
                if (cap.Declaration.ControlRequirements != null)
                {
                    foreach (var req in cap.Declaration.ControlRequirements)
                    {
                        switch (req.Type)
                        {
                            case "cost_ceiling":
                                if (token.Constraints.Budget == null)
                                    unmet.Add("cost_ceiling");
                                break;
                            case "stronger_delegation_required":
                                var tokenHasExplicitBinding = token.Purpose?.Capability == name;
                                if (!tokenHasExplicitBinding)
                                    unmet.Add("stronger_delegation_required");
                                break;
                        }
                    }
                }

                if (unmet.Count > 0)
                {
                    var hasRejectEnforcement = false;
                    if (cap.Declaration.ControlRequirements != null)
                    {
                        foreach (var req in cap.Declaration.ControlRequirements)
                        {
                            if (req.Enforcement == "reject" && unmet.Contains(req.Type))
                            {
                                hasRejectEnforcement = true;
                                break;
                            }
                        }
                    }
                    if (hasRejectEnforcement)
                    {
                        var ctrlResolutionHint = unmet.Contains("cost_ceiling")
                            ? "request_budget_bound_delegation"
                            : "request_capability_binding";
                        restricted.Add(new RestrictedCapability
                        {
                            Capability = name,
                            Reason = $"missing control requirements: {string.Join(", ", unmet)}",
                            ReasonType = "unmet_control_requirement",
                            GrantableBy = rootPrincipal,
                            UnmetTokenRequirements = unmet,
                            ResolutionHint = ctrlResolutionHint,
                        });
                        continue;
                    }
                }

                var constraints = new Dictionary<string, object>();
                foreach (var scopeStr in matchedScopeStrs)
                {
                    if (scopeStr.Contains(":max_$"))
                    {
                        var parts = scopeStr.Split(":max_$", 2);
                        if (parts.Length == 2 && double.TryParse(parts[1], out var maxBudget))
                        {
                            constraints["budget_remaining"] = maxBudget;
                            constraints["currency"] = "USD";
                        }
                    }
                }
                // Include constraints-level budget info if present.
                if (token.Constraints.Budget != null)
                {
                    constraints["budget_remaining"] = token.Constraints.Budget.MaxAmount;
                    constraints["currency"] = token.Constraints.Budget.Currency;
                }

                available.Add(new AvailableCapability
                {
                    Capability = name,
                    ScopeMatch = string.Join(", ", matchedScopeStrs),
                    Constraints = constraints.Count > 0 ? constraints : null,
                });
            }
            else
            {
                // All scope gaps go to restricted — denied is only for non_delegable
                restricted.Add(new RestrictedCapability
                {
                    Capability = name,
                    Reason = $"delegation chain lacks scope(s): {string.Join(", ", missing)}",
                    ReasonType = "insufficient_scope",
                    GrantableBy = rootPrincipal,
                    ResolutionHint = "request_broader_scope",
                });
            }
        }

        return new PermissionResponse
        {
            Available = available,
            Restricted = restricted,
            Denied = denied,
        };
    }

    // --- Audit ---

    /// <summary>
    /// Queries audit entries scoped to the token's root principal.
    /// </summary>
    public AuditResponse QueryAudit(DelegationToken token, AuditFilters filters)
    {
        var rootPrincipal = token.RootPrincipal ?? token.Issuer;
        var resp = AuditLog.QueryAudit(_storage!, rootPrincipal, filters);
        resp.Count = resp.Entries.Count;
        resp.RootPrincipal = rootPrincipal;

        if (!string.IsNullOrEmpty(filters.Capability))
            resp.CapabilityFilter = filters.Capability;
        if (!string.IsNullOrEmpty(filters.Since))
            resp.SinceFilter = filters.Since;

        return resp;
    }

    // --- Checkpoints ---

    /// <summary>Returns a list of checkpoints.</summary>
    public CheckpointListResponse ListCheckpoints(int limit)
    {
        if (limit <= 0) limit = 50;

        var checkpoints = _storage!.ListCheckpoints(limit);
        return new CheckpointListResponse
        {
            Checkpoints = checkpoints,
        };
    }

    /// <summary>Returns a single checkpoint with optional inclusion proof.</summary>
    public CheckpointDetailResponse GetCheckpoint(string id, bool includeProof, int leafIndex)
    {
        var cp = _storage!.GetCheckpointById(id);
        if (cp == null)
        {
            throw new AnipError(Constants.FailureNotFound, $"checkpoint \"{id}\" not found");
        }

        var cpData = JsonSerializer.Serialize(cp, s_serializerOptions);
        var cpMap = JsonSerializer.Deserialize<Dictionary<string, object>>(cpData)!;

        var resp = new CheckpointDetailResponse
        {
            Checkpoint = cpMap,
        };

        if (includeProof)
        {
            var (proof, unavailable) = CheckpointManager.GenerateInclusionProof(_storage!, cp, leafIndex);
            if (unavailable != null)
            {
                resp.ProofUnavailable = unavailable;
            }
            else if (proof != null)
            {
                resp.InclusionProof = new Dictionary<string, object>
                {
                    ["leaf_index"] = leafIndex,
                    ["merkle_root"] = cp.MerkleRoot,
                    ["path"] = proof,
                };
            }
        }

        return resp;
    }

    /// <summary>Creates a new checkpoint from audit entries.</summary>
    public Checkpoint? CreateCheckpoint()
    {
        return CheckpointManager.CreateCheckpoint(_keys!, _storage!, _serviceId);
    }

    // --- Health ---

    /// <summary>Returns the current health status of the service.</summary>
    public HealthReport GetHealth()
    {
        var storageType = _storage is NpgsqlStorage ? "postgres" : "sqlite";
        var connected = _storage != null;
        var status = connected ? "healthy" : "unhealthy";
        var uptime = (DateTime.UtcNow - _startedAt).ToString(@"hh\:mm\:ss");

        return new HealthReport
        {
            Status = status,
            Storage = new StorageHealth
            {
                Connected = connected,
                Type = storageType,
            },
            Uptime = uptime,
            Version = Constants.ProtocolVersion,
        };
    }

    // --- Internal helpers ---

    private void AppendAuditEntry(
        string capability,
        DelegationToken token,
        bool success,
        string? failureType,
        Dictionary<string, object?>? resultSummary,
        CostActual? costActual,
        string invocationId,
        string? clientReferenceId,
        string? taskId,
        string? parentInvocationId,
        string? upstreamService,
        string? sideEffectType,
        string? approvalRequestId = null,
        string? approvalGrantId = null,
        string? entryType = null)
    {
        var rootPrincipal = token.RootPrincipal ?? token.Issuer;
        var eventClass = EventClassification.Classify(sideEffectType, success, failureType);
        var tier = _retentionPolicy.ResolveTier(eventClass);
        var expiresAt = _retentionPolicy.ComputeExpiresAt(tier, DateTime.UtcNow);

        var entry = new AuditEntry
        {
            Capability = capability,
            TokenId = token.TokenId,
            Issuer = token.Issuer,
            Subject = token.Subject,
            RootPrincipal = rootPrincipal,
            Success = success,
            FailureType = failureType,
            ResultSummary = resultSummary?.ToDictionary(kv => kv.Key, kv => (object)kv.Value!),
            CostActual = costActual,
            DelegationChain = new List<string> { token.TokenId },
            InvocationId = invocationId,
            ClientReferenceId = clientReferenceId,
            TaskId = taskId,
            ParentInvocationId = parentInvocationId,
            UpstreamService = upstreamService,
            EventClass = eventClass,
            RetentionTier = tier,
            ExpiresAt = expiresAt,
            ApprovalRequestId = approvalRequestId,
            ApprovalGrantId = approvalGrantId,
            EntryType = entryType,
        };

        // Apply storage-side redaction.
        var entryMap = new Dictionary<string, object?>
        {
            ["event_class"] = entry.EventClass,
            ["parameters"] = entry.Parameters,
        };
        var redacted = StorageRedaction.RedactEntry(entryMap);
        if (redacted.TryGetValue("storage_redacted", out var sr) && sr is true)
        {
            entry.Parameters = null;
            entry.StorageRedacted = true;
        }

        // Route low-value events through aggregator if enabled.
        if (_aggregator != null && eventClass == "malformed_or_spam")
        {
            _aggregator.Submit(EntryToMap(entry));
            return;
        }

        // Best effort - don't fail the invocation if audit logging fails.
        try
        {
            var appended = AuditLog.AppendAudit(_keys!, _storage!, entry);
            if (_hooks?.OnAuditAppend != null)
            {
                ObservabilityHooks.CallHook(() => _hooks.OnAuditAppend(appended.SequenceNumber, capability, invocationId));
            }
        }
        catch
        {
            // Best effort.
        }
    }

    private static Dictionary<string, object?> EntryToMap(AuditEntry entry)
    {
        var m = new Dictionary<string, object?>
        {
            ["timestamp"] = entry.Timestamp,
            ["capability"] = entry.Capability,
            ["actor_key"] = entry.RootPrincipal,
            ["failure_type"] = entry.FailureType,
            ["event_class"] = entry.EventClass,
            ["retention_tier"] = entry.RetentionTier,
            ["expires_at"] = entry.ExpiresAt,
            ["invocation_id"] = entry.InvocationId,
            ["client_reference_id"] = entry.ClientReferenceId,
            ["task_id"] = entry.TaskId,
            ["parent_invocation_id"] = entry.ParentInvocationId,
            ["upstream_service"] = entry.UpstreamService,
            ["token_id"] = entry.TokenId,
            ["issuer"] = entry.Issuer,
            ["subject"] = entry.Subject,
        };

        if (entry.ResultSummary != null && entry.ResultSummary.TryGetValue("detail", out var detail))
        {
            m["detail"] = detail;
        }

        return m;
    }

    // --- Budget/Binding helpers (v0.14) ---

    /// <summary>
    /// Parses a simple ISO 8601 duration string like PT15M, PT1H30M, PT30S.
    /// </summary>
    private static TimeSpan ParseISO8601Duration(string d)
    {
        var match = System.Text.RegularExpressions.Regex.Match(d, @"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?");
        if (!match.Success)
            return TimeSpan.Zero;

        var total = TimeSpan.Zero;
        if (match.Groups[1].Success && int.TryParse(match.Groups[1].Value, out var h))
            total += TimeSpan.FromHours(h);
        if (match.Groups[2].Success && int.TryParse(match.Groups[2].Value, out var m))
            total += TimeSpan.FromMinutes(m);
        if (match.Groups[3].Success && int.TryParse(match.Groups[3].Value, out var s))
            total += TimeSpan.FromSeconds(s);
        return total;
    }

    /// <summary>
    /// Extracts a bound price from params using the capability's binding declarations.
    /// </summary>
    private static double? ResolveBoundPrice(List<BindingRequirement> bindings, Dictionary<string, object?> parameters)
    {
        foreach (var binding in bindings)
        {
            if (parameters.TryGetValue(binding.Field, out var val) && val != null)
            {
                // The binding value may be a dictionary with a "price" key.
                if (val is Dictionary<string, object?> dict)
                {
                    if (dict.TryGetValue("price", out var price))
                    {
                        if (price is double d) return d;
                        if (price is int i) return i;
                        if (price is long l) return l;
                    }
                }
                else if (val is System.Text.Json.JsonElement je && je.ValueKind == System.Text.Json.JsonValueKind.Object)
                {
                    if (je.TryGetProperty("price", out var priceProp) && priceProp.ValueKind == System.Text.Json.JsonValueKind.Number)
                    {
                        return priceProp.GetDouble();
                    }
                }
            }
        }
        return null;
    }

    /// <summary>
    /// Determines the age of a binding value.
    /// Returns a negative TimeSpan if age cannot be determined.
    /// </summary>
    private static TimeSpan ResolveBindingAge(object val)
    {
        var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();

        if (val is Dictionary<string, object?> dict)
        {
            if (dict.TryGetValue("issued_at", out var issuedAt))
            {
                if (issuedAt is double d) return TimeSpan.FromSeconds(now - (long)d);
                if (issuedAt is int i) return TimeSpan.FromSeconds(now - i);
                if (issuedAt is long l) return TimeSpan.FromSeconds(now - l);
            }
        }
        else if (val is System.Text.Json.JsonElement je && je.ValueKind == System.Text.Json.JsonValueKind.Object)
        {
            if (je.TryGetProperty("issued_at", out var issuedProp) && issuedProp.ValueKind == System.Text.Json.JsonValueKind.Number)
            {
                return TimeSpan.FromSeconds(now - issuedProp.GetInt64());
            }
        }

        if (val is string s)
        {
            // Try to extract unix timestamp from format like "qt-hexhex-1234567890"
            var match = System.Text.RegularExpressions.Regex.Match(s, @"-(\d{10,})$");
            if (match.Success && long.TryParse(match.Groups[1].Value, out var ts) && ts > 1000000000)
            {
                return TimeSpan.FromSeconds(now - ts);
            }
        }

        return TimeSpan.FromSeconds(-1);
    }

    private static Dictionary<string, object?> TokenClaimsMap(DelegationToken token)
    {
        var claims = new Dictionary<string, object?>
        {
            ["scope"] = token.Scope,
        };
        if (!string.IsNullOrEmpty(token.CallerClass))
        {
            claims["anip:caller_class"] = token.CallerClass;
        }
        return claims;
    }

    // --- Background workers ---

    private async Task RunRetentionLoop(CancellationToken ct)
    {
        string? holderId = null;
        try
        {
            while (!ct.IsCancellationRequested)
            {
                await Task.Delay(TimeSpan.FromSeconds(_retentionIntervalSeconds), ct);

                holderId = $"retention-{_serviceId}-{DateTime.UtcNow.Ticks}";
                var acquired = _storage!.TryAcquireLeader("retention", holderId, _retentionIntervalSeconds * 2);
                if (!acquired)
                    continue;

                var now = DateTime.UtcNow.ToString("o");
                _storage.DeleteExpiredAuditEntries(now);
            }
        }
        catch (OperationCanceledException)
        {
            // Normal shutdown.
        }
        finally
        {
            if (holderId != null)
                try { _storage?.ReleaseLeader("retention", holderId); }
                catch { /* best effort */ }
        }
    }

    private async Task RunCheckpointLoop(CancellationToken ct)
    {
        var interval = _checkpointPolicy!.IntervalSeconds;
        if (interval <= 0) interval = 60;
        var minEntries = _checkpointPolicy.MinEntries;
        if (minEntries <= 0) minEntries = 1;

        string? holderId = null;

        try
        {
            while (!ct.IsCancellationRequested)
            {
                await Task.Delay(TimeSpan.FromSeconds(interval), ct);

                holderId = $"checkpoint-{_serviceId}-{DateTime.UtcNow.Ticks}";
                var acquired = _storage!.TryAcquireLeader("checkpoint", holderId, interval * 2);
                if (!acquired)
                    continue;

                var maxSeq = _storage.GetMaxAuditSequence();
                if (maxSeq == 0)
                    continue;

                var checkpoints = _storage.ListCheckpoints(100);
                var lastCovered = 0;
                if (checkpoints.Count > 0)
                {
                    var last = checkpoints[^1];
                    if (last.Range.TryGetValue("last_sequence", out var ls))
                        lastCovered = ls;
                }

                var newEntries = maxSeq - lastCovered;
                if (newEntries < minEntries)
                    continue;

                var cp = CreateCheckpoint();
                if (cp != null && _hooks?.OnCheckpointCreated != null)
                {
                    ObservabilityHooks.CallHook(() => _hooks.OnCheckpointCreated(cp.CheckpointId, cp.EntryCount));
                }
            }
        }
        catch (OperationCanceledException)
        {
            // Normal shutdown.
        }
        finally
        {
            if (holderId != null)
                try { _storage?.ReleaseLeader("checkpoint", holderId); }
                catch { /* best effort */ }
        }
    }

    private async Task RunAggregatorFlush(CancellationToken ct)
    {
        try
        {
            while (!ct.IsCancellationRequested)
            {
                await Task.Delay(TimeSpan.FromSeconds(10), ct);
                FlushAggregator();
            }
        }
        catch (OperationCanceledException)
        {
            // Normal shutdown -- do final flush.
            FlushAggregator();
        }
    }

    private void FlushAggregator()
    {
        var results = _aggregator!.Flush(DateTimeOffset.UtcNow);
        foreach (var item in results)
        {
            Dictionary<string, object?> entryData;
            if (item is AggregatedEntry ae)
            {
                entryData = StorageRedaction.RedactEntry(ae.ToAuditDict());
            }
            else if (item is Dictionary<string, object?> dict)
            {
                entryData = StorageRedaction.RedactEntry(dict);
            }
            else
            {
                continue;
            }

            PersistAuditMap(entryData);
        }
    }

    private void PersistAuditMap(Dictionary<string, object?> entryData)
    {
        var entry = new AuditEntry
        {
            Capability = StrVal(entryData, "capability") ?? "",
            Success = false,
            FailureType = StrVal(entryData, "failure_type"),
            EventClass = StrVal(entryData, "event_class"),
            RetentionTier = StrVal(entryData, "retention_tier"),
            ExpiresAt = StrVal(entryData, "expires_at"),
            EntryType = StrVal(entryData, "entry_type") ?? "normal",
            RootPrincipal = StrVal(entryData, "actor_key"),
            Timestamp = StrVal(entryData, "timestamp") ?? "",
            InvocationId = StrVal(entryData, "invocation_id"),
            ClientReferenceId = StrVal(entryData, "client_reference_id"),
            TokenId = StrVal(entryData, "token_id"),
            Issuer = StrVal(entryData, "issuer"),
            Subject = StrVal(entryData, "subject"),
        };

        if (entryData.TryGetValue("grouping_key", out var gk) && gk is Dictionary<string, string> groupingKey)
        {
            entry.GroupingKey = groupingKey;
        }
        if (entryData.TryGetValue("aggregation_window", out var aw) && aw is Dictionary<string, string> aggWindow)
        {
            entry.AggregationWindow = aggWindow;
        }
        if (entryData.TryGetValue("aggregation_count", out var ac) && ac is int aggCount)
        {
            entry.AggregationCount = aggCount;
        }
        entry.FirstSeen = StrVal(entryData, "first_seen");
        entry.LastSeen = StrVal(entryData, "last_seen");
        entry.RepresentativeDetail = StrVal(entryData, "representative_detail");

        try
        {
            AuditLog.AppendAudit(_keys!, _storage!, entry);
        }
        catch
        {
            // Best effort.
        }
    }

    private static string? StrVal(Dictionary<string, object?> m, string key)
    {
        return m.TryGetValue(key, out var val) ? val as string : null;
    }
}
