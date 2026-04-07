package dev.anip.server;

import dev.anip.core.ANIPError;
import dev.anip.core.Constants;
import dev.anip.core.DelegationToken;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;
import dev.anip.crypto.KeyManager;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class DelegationEngineTest {

    private KeyManager km;
    private SqliteStorage storage;
    private static final String SERVICE_ID = "test-service";

    @BeforeEach
    void setUp() throws Exception {
        km = KeyManager.create(null);
        storage = new SqliteStorage(":memory:");
    }

    @AfterEach
    void tearDown() throws Exception {
        storage.close();
    }

    @Test
    void issueAndResolveRoundTrip() throws Exception {
        TokenRequest req = new TokenRequest(
                "agent@example.com",
                List.of("travel.search", "travel.book"),
                "search_flights",
                Map.of("origin", "SFO"),
                null, 2, "human"
        );

        TokenResponse resp = DelegationEngine.issueDelegationToken(
                km, storage, SERVICE_ID, "human@example.com", req);

        assertTrue(resp.isIssued());
        assertNotNull(resp.getTokenId());
        assertNotNull(resp.getToken());
        assertNotNull(resp.getExpires());
        assertTrue(resp.getTokenId().startsWith("anip-"));

        // Resolve the token.
        DelegationToken resolved = DelegationEngine.resolveBearerToken(
                km, storage, SERVICE_ID, resp.getToken());

        assertNotNull(resolved);
        assertEquals(resp.getTokenId(), resolved.getTokenId());
        assertEquals("agent@example.com", resolved.getSubject());
        assertEquals("human@example.com", resolved.getRootPrincipal());
        assertEquals(List.of("travel.search", "travel.book"), resolved.getScope());
    }

    @Test
    void issueDefaultSubjectToPrincipal() throws Exception {
        TokenRequest req = new TokenRequest(
                null, // no subject
                List.of("travel.search"), "search_flights",
                null, null, 0, null
        );

        TokenResponse resp = DelegationEngine.issueDelegationToken(
                km, storage, SERVICE_ID, "human@example.com", req);

        DelegationToken token = storage.loadToken(resp.getTokenId());
        assertNotNull(token);
        assertEquals("human@example.com", token.getSubject());
    }

    @Test
    void issueDefaultTtl() throws Exception {
        TokenRequest req = new TokenRequest(
                "agent", List.of("scope"), "cap", null, null, 0, null
        );

        TokenResponse resp = DelegationEngine.issueDelegationToken(
                km, storage, SERVICE_ID, "principal", req);

        assertTrue(resp.isIssued());
        assertNotNull(resp.getExpires());
    }

    @Test
    void issueWithParentToken() throws Exception {
        // Issue a root token first.
        TokenRequest rootReq = new TokenRequest(
                "agent1", List.of("travel.search"), "search_flights",
                null, null, 2, "human"
        );
        TokenResponse rootResp = DelegationEngine.issueDelegationToken(
                km, storage, SERVICE_ID, "human@example.com", rootReq);

        // Issue a sub-delegation using the root token ID.
        TokenRequest subReq = new TokenRequest(
                "agent2", List.of("travel.search"), "search_flights",
                null, rootResp.getTokenId(), 1, "agent"
        );
        TokenResponse subResp = DelegationEngine.issueDelegationToken(
                km, storage, SERVICE_ID, "agent1", subReq);

        assertTrue(subResp.isIssued());

        DelegationToken subToken = storage.loadToken(subResp.getTokenId());
        assertNotNull(subToken);
        assertEquals("human@example.com", subToken.getRootPrincipal());
        assertEquals(rootResp.getTokenId(), subToken.getParent());
    }

    @Test
    void issueWithInvalidParentToken() {
        TokenRequest req = new TokenRequest(
                "agent", List.of("scope"), "cap",
                null, "nonexistent-token-id", 2, "human"
        );

        ANIPError error = assertThrows(ANIPError.class, () ->
                DelegationEngine.issueDelegationToken(km, storage, SERVICE_ID, "principal", req));
        assertEquals(Constants.FAILURE_INVALID_TOKEN, error.getErrorType());
    }

    @Test
    void resolveInvalidJwt() {
        ANIPError error = assertThrows(ANIPError.class, () ->
                DelegationEngine.resolveBearerToken(km, storage, SERVICE_ID, "not.a.jwt"));
        assertEquals(Constants.FAILURE_INVALID_TOKEN, error.getErrorType());
    }

    @Test
    void resolveTokenNotInStorage() throws Exception {
        // Create a valid JWT but don't store the token.
        Map<String, Object> claims = Map.of(
                "jti", "missing-token",
                "iss", SERVICE_ID,
                "sub", "test",
                "aud", SERVICE_ID,
                "iat", System.currentTimeMillis() / 1000,
                "exp", System.currentTimeMillis() / 1000 + 3600
        );
        String jwt = dev.anip.crypto.JwtSigner.signDelegationJwt(km, claims);

        ANIPError error = assertThrows(ANIPError.class, () ->
                DelegationEngine.resolveBearerToken(km, storage, SERVICE_ID, jwt));
        assertEquals(Constants.FAILURE_INVALID_TOKEN, error.getErrorType());
        assertTrue(error.getDetail().contains("not found"));
    }

    // --- Scope validation ---

    @Test
    void validateScopeSufficient() throws Exception {
        DelegationToken token = createTokenWithScope(List.of("travel.search", "travel.book"));
        // Should not throw.
        DelegationEngine.validateScope(token, List.of("travel.search"));
    }

    @Test
    void validateScopeHierarchical() throws Exception {
        DelegationToken token = createTokenWithScope(List.of("travel"));
        // "travel" should cover "travel.search".
        DelegationEngine.validateScope(token, List.of("travel.search"));
    }

    @Test
    void validateScopeInsufficient() throws Exception {
        DelegationToken token = createTokenWithScope(List.of("travel.search"));
        ANIPError error = assertThrows(ANIPError.class, () ->
                DelegationEngine.validateScope(token, List.of("admin")));
        assertEquals(Constants.FAILURE_SCOPE_INSUFFICIENT, error.getErrorType());
        assertNotNull(error.getResolution());
        assertEquals("request_broader_scope", error.getResolution().getAction());
    }

    @Test
    void validateScopeWithModifier() throws Exception {
        // Token has "travel.search:read" — base is "travel.search".
        DelegationToken token = createTokenWithScope(List.of("travel.search:read"));
        DelegationEngine.validateScope(token, List.of("travel.search"));
    }

    @Test
    void validateScopeEmptyMinimum() throws Exception {
        DelegationToken token = createTokenWithScope(List.of("travel.search"));
        // Empty minimum scope should pass.
        DelegationEngine.validateScope(token, List.of());
        DelegationEngine.validateScope(token, null);
    }

    // --- task_id echoed in issuance response ---

    @Test
    void issueWithCallerTaskId_echoedInResponse() throws Exception {
        TokenRequest req = new TokenRequest(
                "agent@example.com",
                List.of("travel.search"),
                "search_flights",
                Map.of("task_id", "my-custom-task"),
                null, 2, null
        );

        TokenResponse resp = DelegationEngine.issueDelegationToken(
                km, storage, SERVICE_ID, "human@example.com", req);

        assertTrue(resp.isIssued());
        assertEquals("my-custom-task", resp.getTaskId());
    }

    @Test
    void issueWithoutPurposeParams_autoGeneratedTaskId() throws Exception {
        TokenRequest req = new TokenRequest(
                "agent@example.com",
                List.of("travel.search"),
                "search_flights",
                null, // no purpose_parameters
                null, 2, null
        );

        TokenResponse resp = DelegationEngine.issueDelegationToken(
                km, storage, SERVICE_ID, "human@example.com", req);

        assertTrue(resp.isIssued());
        assertNotNull(resp.getTaskId());
        assertTrue(resp.getTaskId().startsWith("task-"));
    }

    @Test
    void issueWithPurposeParamsNoTaskId_responseOmitsTaskId() throws Exception {
        TokenRequest req = new TokenRequest(
                "agent@example.com",
                List.of("travel.search"),
                "search_flights",
                Map.of("source", "test"), // purpose_parameters without task_id
                null, 2, null
        );

        TokenResponse resp = DelegationEngine.issueDelegationToken(
                km, storage, SERVICE_ID, "human@example.com", req);

        assertTrue(resp.isIssued());
        assertNull(resp.getTaskId());
    }

    // --- Helpers ---

    private DelegationToken createTokenWithScope(List<String> scope) {
        return new DelegationToken(
                "tok-test", SERVICE_ID, "subject", scope,
                new dev.anip.core.Purpose("cap", Map.of(), "task"),
                "", "2030-12-31T23:59:59Z",
                new dev.anip.core.DelegationConstraints(), "principal", "human"
        );
    }
}
