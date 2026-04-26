package dev.anip.servicetest;

import dev.anip.core.ANIPError;
import dev.anip.core.ApprovalGrant;
import dev.anip.core.ApprovalRequest;
import dev.anip.core.ApprovalRequiredMetadata;
import dev.anip.core.AuditPolicy;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.Composition;
import dev.anip.core.CompositionStep;
import dev.anip.core.FailurePolicy;
import dev.anip.core.GrantPolicy;
import dev.anip.core.IssueApprovalGrantRequest;
import dev.anip.core.IssueApprovalGrantResponse;
import dev.anip.core.SideEffect;
import dev.anip.service.InvokeOpts;

import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class V023ModelsTest {

    private GrantPolicy grantPolicy() {
        return new GrantPolicy(Arrays.asList("one_time", "session_bound"), "one_time", 900, 1);
    }

    @Test
    void capabilityKindAtomicByDefault() {
        CapabilityDeclaration d = new CapabilityDeclaration(
                "cap", "d", "1.0",
                Collections.<CapabilityInput>emptyList(),
                new CapabilityOutput("x", Collections.<String>emptyList()),
                new SideEffect("read", "not_applicable"),
                Arrays.asList("s"),
                null, null, null);
        assertEquals("atomic", d.getKind());
        assertNull(d.getComposition());
        assertNull(d.getGrantPolicy());
    }

    @Test
    void composedDeclarationCarriesAllFields() {
        Map<String, Map<String, String>> inputMapping = new HashMap<>();
        Map<String, String> selectMap = new HashMap<>();
        selectMap.put("quarter", "$.input.quarter");
        inputMapping.put("select", selectMap);
        Map<String, String> enrichMap = new HashMap<>();
        enrichMap.put("accounts", "$.steps.select.output.accounts");
        inputMapping.put("enrich", enrichMap);

        Map<String, String> outputMapping = new HashMap<>();
        outputMapping.put("count", "$.steps.enrich.output.count");

        Map<String, Object> emptyOut = new HashMap<>();
        emptyOut.put("count", 0);
        emptyOut.put("accounts", Collections.emptyList());

        Composition comp = new Composition(
                "same_service",
                Arrays.asList(
                        new CompositionStep("select", "select_at_risk").setEmptyResultSource(true),
                        new CompositionStep("enrich", "enrich_accounts")),
                inputMapping,
                outputMapping,
                new FailurePolicy(),
                new AuditPolicy(true, true)
        )
                .setEmptyResultPolicy("return_success_no_results")
                .setEmptyResultOutput(emptyOut);

        CapabilityDeclaration d = new CapabilityDeclaration(
                "summary", "d", "1.0",
                Collections.<CapabilityInput>emptyList(),
                new CapabilityOutput("x", Collections.<String>emptyList()),
                new SideEffect("read", "not_applicable"),
                Arrays.asList("gtm.read"),
                null, null, null)
                .setKind("composed")
                .setComposition(comp)
                .setGrantPolicy(grantPolicy());

        assertEquals("composed", d.getKind());
        assertNotNull(d.getComposition());
        assertEquals("same_service", d.getComposition().getAuthorityBoundary());
        assertEquals(2, d.getComposition().getSteps().size());
        assertTrue(d.getComposition().getSteps().get(0).isEmptyResultSource());
        assertFalse(d.getComposition().getSteps().get(1).isEmptyResultSource());
        assertEquals("return_success_no_results", d.getComposition().getEmptyResultPolicy());
        assertEquals("fail_parent", d.getComposition().getFailurePolicy().getChildError());
        assertEquals("propagate", d.getComposition().getFailurePolicy().getChildClarification());
        assertNotNull(d.getGrantPolicy());
    }

    @Test
    void approvalRequestPendingState() {
        Map<String, Object> requester = new HashMap<>();
        requester.put("principal", "u1");
        ApprovalRequest r = new ApprovalRequest(
                "apr_test", "cap", Arrays.asList("s"), requester,
                new HashMap<>(), "d2",
                new HashMap<>(), "d1",
                grantPolicy(),
                ApprovalRequest.STATUS_PENDING,
                "2026-01-01T00:00:00Z", "2026-01-01T00:15:00Z");
        assertEquals("pending", r.getStatus());
        assertNull(r.getApprover());
        assertNull(r.getDecidedAt());
    }

    @Test
    void approvalRequestExpiredHasNoApprover() {
        ApprovalRequest r = new ApprovalRequest(
                "apr_test", "cap", Arrays.asList("s"), new HashMap<>(),
                new HashMap<>(), "d2", new HashMap<>(), "d1",
                grantPolicy(),
                ApprovalRequest.STATUS_PENDING,
                "2026-01-01T00:00:00Z", "2026-01-01T00:15:00Z")
                .setStatus(ApprovalRequest.STATUS_EXPIRED)
                .setDecidedAt("2026-01-01T00:15:01Z");
        assertEquals("expired", r.getStatus());
        assertNull(r.getApprover());
        assertNotNull(r.getDecidedAt());
    }

    @Test
    void approvalGrantOneTime() {
        Map<String, Object> requester = new HashMap<>();
        requester.put("principal", "u1");
        Map<String, Object> approver = new HashMap<>();
        approver.put("principal", "u2");
        ApprovalGrant g = new ApprovalGrant(
                "grant_test", "apr_test", ApprovalGrant.TYPE_ONE_TIME,
                "finance.transfer_funds", Arrays.asList("finance.write"),
                "sha256:params", "sha256:preview",
                requester, approver,
                "2026-01-01T00:00:00Z", "2026-01-01T00:15:00Z",
                1, 0, null, "sig_test");
        assertEquals("apr_test", g.getApprovalRequestId());
        assertEquals("one_time", g.getGrantType());
        assertNull(g.getSessionId());
        assertEquals(0, g.getUseCount());
    }

    @Test
    void approvalGrantSessionBound() {
        ApprovalGrant g = new ApprovalGrant(
                "grant_test", "apr_test", ApprovalGrant.TYPE_SESSION_BOUND,
                "cap", Arrays.asList("s"),
                "d1", "d2", new HashMap<>(), new HashMap<>(),
                "2026-01-01T00:00:00Z", "2026-01-01T00:15:00Z",
                5, 0, "sess_1", "sig");
        assertEquals("session_bound", g.getGrantType());
        assertEquals("sess_1", g.getSessionId());
        assertEquals(5, g.getMaxUses());
    }

    @Test
    void anipErrorWithApprovalRequiredMetadata() {
        ApprovalRequiredMetadata md = new ApprovalRequiredMetadata(
                "apr_test", "d2", "d1", grantPolicy());
        ANIPError e = new ANIPError("approval_required", "needs approval")
                .withResolution("contact_service_owner")
                .withApprovalRequired(md);
        assertNotNull(e.getApprovalRequired());
        assertEquals("apr_test", e.getApprovalRequired().getApprovalRequestId());
        assertEquals(900, e.getApprovalRequired().getGrantPolicy().getExpiresInSeconds());
    }

    @Test
    void anipErrorWithoutApprovalRequiredIsNull() {
        ANIPError e = new ANIPError("budget_exceeded", "too expensive")
                .withResolution("request_budget_increase");
        assertNull(e.getApprovalRequired());
    }

    @Test
    void invokeOptsCarriesApprovalGrant() {
        InvokeOpts opts = new InvokeOpts().setApprovalGrant("grant_test");
        assertEquals("grant_test", opts.getApprovalGrant());
    }

    @Test
    void invokeOptsApprovalGrantDefaultsToNull() {
        InvokeOpts opts = new InvokeOpts();
        assertNull(opts.getApprovalGrant());
    }

    @Test
    void issueApprovalGrantRequestRoundTrip() {
        IssueApprovalGrantRequest req = new IssueApprovalGrantRequest("apr_test", "one_time")
                .setExpiresInSeconds(600).setMaxUses(1);
        assertEquals("apr_test", req.getApprovalRequestId());
        assertEquals("one_time", req.getGrantType());
        assertEquals(Integer.valueOf(600), req.getExpiresInSeconds());
        assertEquals(Integer.valueOf(1), req.getMaxUses());
    }

    @Test
    void grantPolicyConstructorRejectsDefaultNotInAllowed() {
        IllegalArgumentException ex = assertThrows(
                IllegalArgumentException.class,
                () -> new GrantPolicy(Arrays.asList("one_time"), "session_bound", 900, 1));
        assertTrue(ex.getMessage().contains("defaultGrantType"));
    }

    @Test
    void grantPolicyConstructorRejectsEmptyAllowed() {
        assertThrows(
                IllegalArgumentException.class,
                () -> new GrantPolicy(Collections.<String>emptyList(), "one_time", 900, 1));
    }

    @Test
    void grantPolicyConstructorAcceptsDefaultInAllowed() {
        GrantPolicy p = new GrantPolicy(
                Arrays.asList("one_time", "session_bound"), "session_bound", 900, 1);
        assertEquals("session_bound", p.getDefaultGrantType());
    }

    @Test
    void issueApprovalGrantResponseWrapsGrant() {
        ApprovalGrant g = new ApprovalGrant(
                "grant_test", "apr_test", "one_time",
                "cap", Arrays.asList("s"),
                "d1", "d2", new HashMap<>(), new HashMap<>(),
                "2026-01-01T00:00:00Z", "2026-01-01T00:15:00Z",
                1, 0, null, "sig");
        IssueApprovalGrantResponse resp = new IssueApprovalGrantResponse(g);
        assertEquals("grant_test", resp.getGrant().getGrantId());
    }
}
