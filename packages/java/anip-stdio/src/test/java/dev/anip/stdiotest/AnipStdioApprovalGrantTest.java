package dev.anip.stdiotest;

import dev.anip.core.ANIPError;
import dev.anip.core.ApprovalGrant;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.Constants;
import dev.anip.core.GrantPolicy;
import dev.anip.core.SideEffect;
import dev.anip.core.TokenRequest;
import dev.anip.service.ANIPService;
import dev.anip.service.CapabilityDef;
import dev.anip.service.ServiceConfig;
import dev.anip.stdio.AnipStdioServer;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

/** SPEC.md §4.8: stdio carries approval_grant on anip.invoke, validated as over HTTP. */
class AnipStdioApprovalGrantTest {

    private ANIPService service;
    private AnipStdioServer server;
    private String token;

    @BeforeEach
    void setUp() throws Exception {
        CapabilityDeclaration decl = new CapabilityDeclaration(
                "transfer", "Transfer funds", "1.0",
                List.of(new CapabilityInput("amount", "number", true, null, "amount")),
                new CapabilityOutput("object", List.of("transferred")),
                new SideEffect("irreversible", "none"),
                List.of("finance.write"), null, null, List.of("sync", "streaming"))
                .setGrantPolicy(new GrantPolicy(List.of("one_time"), "one_time", 900, 1));
        service = new ANIPService(new ServiceConfig()
                .setServiceId("stdio-approvals")
                .setCapabilities(List.of(new CapabilityDef(decl, (ctx, params) -> {
                    if (((Number) params.get("amount")).doubleValue() > 1000 && ctx.getApprovalGrant() == null) {
                        throw new ANIPError(Constants.FAILURE_APPROVAL_REQUIRED, "transfers above 1000 need approval");
                    }
                    return Map.of("transferred", params.get("amount"));
                })))
                .setStorage(":memory:")
                .setAuthenticate(b -> "test-api-key".equals(b) ? Optional.of("user@test.com") : Optional.empty())
                .setRetentionIntervalSeconds(-1));
        service.start();
        server = new AnipStdioServer(service);
        token = service.issueToken("user@test.com", new TokenRequest(
                "user@test.com", List.of("finance.write"), "transfer", null, null, 1, null)).getToken();
    }

    @AfterEach
    void tearDown() {
        if (service != null) service.shutdown();
    }

    /** The failure type of the call, or null when it succeeded. */
    @SuppressWarnings("unchecked")
    private String invoke(Map<String, Object> extra) {
        Map<String, Object> params = new LinkedHashMap<>();
        params.put("auth", Map.of("bearer", token));
        params.put("capability", "transfer");
        params.put("parameters", Map.of("amount", 5000));
        params.putAll(extra);
        Map<String, Object> msg = new LinkedHashMap<>();
        msg.put("jsonrpc", "2.0");
        msg.put("id", 1);
        msg.put("method", "anip.invoke");
        msg.put("params", params);
        Object raw = server.handleRequest(msg);
        Map<String, Object> response;
        if (raw instanceof List<?> list) {
            response = (Map<String, Object>) list.get(list.size() - 1);
        } else if (raw instanceof Object[] array) {
            response = (Map<String, Object>) array[array.length - 1];
        } else {
            response = (Map<String, Object>) raw;
        }
        if (response.get("error") != null) {
            Map<String, Object> data = (Map<String, Object>) ((Map<String, Object>) response.get("error")).get("data");
            return data == null ? "rpc_error" : (String) data.get("type");
        }
        Map<String, Object> result = (Map<String, Object>) response.get("result");
        if (Boolean.TRUE.equals(result.get("success"))) return null;
        lastFailure = (Map<String, Object>) result.get("failure");
        return (String) lastFailure.get("type");
    }

    private Map<String, Object> lastFailure;

    @Test
    @SuppressWarnings("unchecked")
    void continuationRunsWithTheGrant() throws Exception {
        assertEquals("approval_required", invoke(Map.of()));
        Map<String, Object> meta = (Map<String, Object>) lastFailure.get("approval_required");
        ApprovalGrant grant = service.issueApprovalGrant((String) meta.get("approval_request_id"), "one_time",
                Map.of("subject", "approver"), null, null, null);

        assertNull(invoke(Map.of("approval_grant", grant.getGrantId())));
        assertEquals("grant_consumed", invoke(Map.of("approval_grant", grant.getGrantId())));
    }

    @Test
    void blankGrantIsNotFound() {
        for (boolean stream : List.of(false, true)) {
            for (Object grant : Arrays.asList("", "   ", 7)) {
                assertEquals("grant_not_found", invoke(Map.of("approval_grant", grant, "stream", stream)),
                        "stream=" + stream + " approval_grant=" + grant);
            }
        }
    }

    @Test
    void nullGrantIsNoGrant() {
        Map<String, Object> extra = new HashMap<>();
        extra.put("approval_grant", null);
        assertEquals("approval_required", invoke(extra));
    }
}
