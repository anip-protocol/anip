using System.Text.Json;

namespace Anip.Core.Tests;

/// <summary>
/// Tests for CrossServiceContract, CrossServiceContractEntry, and RecoveryTarget (v0.21).
/// </summary>
public class CrossServiceContractTests
{
    // --- CrossServiceContractEntry ---

    [Fact]
    public void CrossServiceContractEntry_FieldsArePreserved()
    {
        var entry = new CrossServiceContractEntry
        {
            Target = new ServiceCapabilityRef { Service = "booking-service", Capability = "confirm_booking" },
            RequiredForTaskCompletion = true,
            Continuity = "same_task",
            CompletionMode = "downstream_acceptance",
        };

        Assert.Equal("booking-service", entry.Target.Service);
        Assert.Equal("confirm_booking", entry.Target.Capability);
        Assert.True(entry.RequiredForTaskCompletion);
        Assert.Equal("same_task", entry.Continuity);
        Assert.Equal("downstream_acceptance", entry.CompletionMode);
    }

    [Fact]
    public void CrossServiceContractEntry_SerializesToSnakeCaseJson()
    {
        var entry = new CrossServiceContractEntry
        {
            Target = new ServiceCapabilityRef { Service = "svc", Capability = "cap" },
            RequiredForTaskCompletion = true,
            Continuity = "same_task",
            CompletionMode = "downstream_acceptance",
        };

        var json = JsonSerializer.Serialize(entry);
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;

        Assert.True(root.TryGetProperty("target", out _));
        Assert.True(root.TryGetProperty("required_for_task_completion", out var rfTc));
        Assert.True(rfTc.GetBoolean());
        Assert.True(root.TryGetProperty("continuity", out _));
        Assert.True(root.TryGetProperty("completion_mode", out var cm));
        Assert.Equal("downstream_acceptance", cm.GetString());
    }

    [Fact]
    public void CrossServiceContractEntry_DeserializesFromJson()
    {
        var json = """
            {
                "target": { "service": "booking-service", "capability": "confirm_booking" },
                "required_for_task_completion": true,
                "continuity": "same_task",
                "completion_mode": "downstream_acceptance"
            }
            """;

        var entry = JsonSerializer.Deserialize<CrossServiceContractEntry>(json);

        Assert.NotNull(entry);
        Assert.Equal("booking-service", entry!.Target.Service);
        Assert.Equal("confirm_booking", entry.Target.Capability);
        Assert.True(entry.RequiredForTaskCompletion);
        Assert.Equal("downstream_acceptance", entry.CompletionMode);
    }

    // --- CrossServiceContract ---

    [Fact]
    public void CrossServiceContract_DefaultsToEmptyLists()
    {
        var contract = new CrossServiceContract();

        Assert.NotNull(contract.Handoff);
        Assert.Empty(contract.Handoff);
        Assert.NotNull(contract.Followup);
        Assert.Empty(contract.Followup);
        Assert.NotNull(contract.Verification);
        Assert.Empty(contract.Verification);
    }

    [Fact]
    public void CrossServiceContract_RoundTripsWithHandoffEntries()
    {
        var contract = new CrossServiceContract
        {
            Handoff = new List<CrossServiceContractEntry>
            {
                new()
                {
                    Target = new ServiceCapabilityRef { Service = "booking-service", Capability = "confirm_booking" },
                    RequiredForTaskCompletion = true,
                    Continuity = "same_task",
                    CompletionMode = "downstream_acceptance",
                }
            }
        };

        var json = JsonSerializer.Serialize(contract);
        var restored = JsonSerializer.Deserialize<CrossServiceContract>(json);

        Assert.NotNull(restored);
        Assert.Single(restored!.Handoff);
        Assert.Equal("booking-service", restored.Handoff[0].Target.Service);
        Assert.True(restored.Handoff[0].RequiredForTaskCompletion);
        Assert.Empty(restored.Followup);
        Assert.Empty(restored.Verification);
    }

    // --- RecoveryTarget ---

    [Fact]
    public void RecoveryTarget_DefaultContinuity()
    {
        var rt = new RecoveryTarget { Kind = "refresh" };
        Assert.Equal("same_task", rt.Continuity);
    }

    [Fact]
    public void RecoveryTarget_NullableTarget()
    {
        var rt = new RecoveryTarget { Kind = "escalation" };
        Assert.Null(rt.Target);
    }

    [Fact]
    public void RecoveryTarget_RoundTripsWithTarget()
    {
        var rt = new RecoveryTarget
        {
            Kind = "refresh",
            Target = new ServiceCapabilityRef { Service = "auth-service", Capability = "refresh_token" },
            Continuity = "same_task",
            RetryAfterTarget = true,
        };

        var json = JsonSerializer.Serialize(rt);
        var restored = JsonSerializer.Deserialize<RecoveryTarget>(json);

        Assert.NotNull(restored);
        Assert.Equal("refresh", restored!.Kind);
        Assert.NotNull(restored.Target);
        Assert.Equal("auth-service", restored.Target!.Service);
        Assert.Equal("refresh_token", restored.Target.Capability);
        Assert.True(restored.RetryAfterTarget);
    }

    [Fact]
    public void RecoveryTarget_SerializesToSnakeCaseJson()
    {
        var rt = new RecoveryTarget
        {
            Kind = "redelegation",
            RetryAfterTarget = true,
        };

        var json = JsonSerializer.Serialize(rt);
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;

        Assert.True(root.TryGetProperty("kind", out var kind));
        Assert.Equal("redelegation", kind.GetString());
        Assert.True(root.TryGetProperty("retry_after_target", out var rat));
        Assert.True(rat.GetBoolean());
    }

    [Fact]
    public void RecoveryTarget_AllKindsAccepted()
    {
        foreach (var kind in new[] { "refresh", "redelegation", "revalidation", "escalation" })
        {
            var rt = new RecoveryTarget { Kind = kind };
            Assert.Equal(kind, rt.Kind);
        }
    }

    // --- CapabilityDeclaration with cross_service_contract ---

    [Fact]
    public void CapabilityDeclaration_CrossServiceContractNullByDefault()
    {
        var decl = new CapabilityDeclaration { Name = "test" };
        Assert.Null(decl.CrossServiceContract);
    }

    [Fact]
    public void CapabilityDeclaration_WithCrossServiceContract_SerializesCorrectly()
    {
        var decl = new CapabilityDeclaration
        {
            Name = "search_flights",
            Description = "Search for flights",
            ContractVersion = "1.0",
            CrossServiceContract = new CrossServiceContract
            {
                Handoff = new List<CrossServiceContractEntry>
                {
                    new()
                    {
                        Target = new ServiceCapabilityRef { Service = "booking-service", Capability = "confirm_booking" },
                        RequiredForTaskCompletion = true,
                        Continuity = "same_task",
                        CompletionMode = "downstream_acceptance",
                    }
                }
            }
        };

        var json = JsonSerializer.Serialize(decl);
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;

        Assert.True(root.TryGetProperty("cross_service_contract", out var csc));
        Assert.True(csc.TryGetProperty("handoff", out var handoff));
        Assert.Equal(1, handoff.GetArrayLength());
        var first = handoff[0];
        Assert.True(first.TryGetProperty("target", out var target));
        Assert.Equal("booking-service", target.GetProperty("service").GetString());
    }

    // --- Resolution with recovery_target ---

    [Fact]
    public void Resolution_RecoveryTargetNullByDefault()
    {
        var resolution = new Resolution { Action = "request_broader_scope" };
        Assert.Null(resolution.RecoveryTarget);
    }

    [Fact]
    public void Resolution_WithRecoveryTarget_SerializesCorrectly()
    {
        var resolution = new Resolution
        {
            Action = "refresh_token",
            RecoveryClass = "refresh_then_retry",
            RecoveryTarget = new RecoveryTarget
            {
                Kind = "refresh",
                Target = new ServiceCapabilityRef { Service = "auth-service", Capability = "refresh_token" },
                Continuity = "same_task",
                RetryAfterTarget = true,
            }
        };

        var json = JsonSerializer.Serialize(resolution);
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;

        Assert.True(root.TryGetProperty("recovery_target", out var rt));
        Assert.Equal("refresh", rt.GetProperty("kind").GetString());
        Assert.Equal("auth-service", rt.GetProperty("target").GetProperty("service").GetString());
        Assert.True(rt.GetProperty("retry_after_target").GetBoolean());
    }

    [Fact]
    public void Resolution_WithRecoveryTarget_RoundTrips()
    {
        var resolution = new Resolution
        {
            Action = "refresh_token",
            RecoveryClass = "refresh_then_retry",
            RecoveryTarget = new RecoveryTarget
            {
                Kind = "refresh",
                Target = new ServiceCapabilityRef { Service = "auth-service", Capability = "refresh_token" },
                Continuity = "same_task",
                RetryAfterTarget = true,
            }
        };

        var json = JsonSerializer.Serialize(resolution);
        var restored = JsonSerializer.Deserialize<Resolution>(json);

        Assert.NotNull(restored);
        Assert.NotNull(restored!.RecoveryTarget);
        Assert.Equal("refresh", restored.RecoveryTarget!.Kind);
        Assert.NotNull(restored.RecoveryTarget.Target);
        Assert.Equal("auth-service", restored.RecoveryTarget.Target!.Service);
        Assert.True(restored.RecoveryTarget.RetryAfterTarget);
    }
}
