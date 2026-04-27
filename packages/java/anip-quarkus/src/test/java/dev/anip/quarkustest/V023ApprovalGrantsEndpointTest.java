package dev.anip.quarkustest;

import dev.anip.core.ApprovalRequest;
import dev.anip.core.GrantPolicy;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;
import dev.anip.server.SqliteStorage;
import dev.anip.service.ANIPService;
import dev.anip.service.V023;

import io.quarkus.test.junit.QuarkusTest;
import jakarta.inject.Inject;
import org.junit.jupiter.api.*;

import java.util.List;
import java.util.Map;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

/**
 * v0.23 — POST /anip/approval_grants endpoint tests. SPEC.md §4.9.
 */
@QuarkusTest
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class V023ApprovalGrantsEndpointTest {

    @Inject
    ANIPService service;

    private String approverJwt;

    @BeforeAll
    void setUp() throws Exception {
        // Issue a token whose scope grants approver:* — broad approver authority.
        TokenRequest req = new TokenRequest(
                "approver:test", List.of("approver:*"), null,
                null, null, 0, null);
        TokenResponse resp = service.issueToken("approver@test.com", req);
        approverJwt = resp.getToken();
    }

    /** Test helper — directly persist an ApprovalRequest the endpoint can redeem. */
    private String persistRequest(String id, GrantPolicy gp) throws Exception {
        SqliteStorage storage = (SqliteStorage) service.getStorage();
        ApprovalRequest req = new ApprovalRequest(
                id, "search_flights", List.of("travel"),
                Map.of("subject", "alice"), null,
                Map.of(), V023.sha256Digest(Map.of()),
                Map.of("origin", "SEA"), V023.sha256Digest(Map.of("origin", "SEA")),
                gp, ApprovalRequest.STATUS_PENDING, null, null,
                V023.utcNowIso(), V023.utcInIso(900));
        storage.storeApprovalRequest(req);
        return id;
    }

    @Test
    void discoveryAdvertisesEndpoint() {
        given().when().get("/.well-known/anip")
            .then().statusCode(200)
            .body("anip_discovery.endpoints.approval_grants", equalTo("/anip/approval_grants"));
    }

    @Test
    void unauthenticatedReturns401() {
        given().contentType("application/json")
            .body("{\"approval_request_id\":\"x\",\"grant_type\":\"one_time\"}")
            .when().post("/anip/approval_grants")
            .then().statusCode(401);
    }

    @Test
    void malformedJsonReturns400Or415() {
        given().contentType("application/json")
            .header("Authorization", "Bearer " + approverJwt)
            .body("{not json")
            .when().post("/anip/approval_grants")
            .then().statusCode(anyOf(equalTo(400), equalTo(415)));
    }

    @Test
    void missingApprovalRequestIdReturns400() {
        given().contentType("application/json")
            .header("Authorization", "Bearer " + approverJwt)
            .body("{\"grant_type\":\"one_time\"}")
            .when().post("/anip/approval_grants")
            .then().statusCode(400)
            .body("failure.type", equalTo("invalid_parameters"));
    }

    @Test
    void invalidGrantTypeReturns400() throws Exception {
        String id = persistRequest("apr_invtype",
                new GrantPolicy(List.of("one_time"), "one_time", 600, 1));
        given().contentType("application/json")
            .header("Authorization", "Bearer " + approverJwt)
            .body("{\"approval_request_id\":\"" + id + "\",\"grant_type\":\"foo\"}")
            .when().post("/anip/approval_grants")
            .then().statusCode(400);
    }

    @Test
    void emptySessionIdForSessionBoundReturns400() throws Exception {
        String id = persistRequest("apr_emptysess",
                new GrantPolicy(List.of("session_bound"), "session_bound", 600, 1));
        given().contentType("application/json")
            .header("Authorization", "Bearer " + approverJwt)
            .body("{\"approval_request_id\":\"" + id + "\",\"grant_type\":\"session_bound\",\"session_id\":\"\"}")
            .when().post("/anip/approval_grants")
            .then().statusCode(400);
    }

    @Test
    void zeroExpiresInSecondsRejected() throws Exception {
        String id = persistRequest("apr_zeroexp",
                new GrantPolicy(List.of("one_time"), "one_time", 600, 1));
        given().contentType("application/json")
            .header("Authorization", "Bearer " + approverJwt)
            .body("{\"approval_request_id\":\"" + id + "\",\"grant_type\":\"one_time\",\"expires_in_seconds\":0}")
            .when().post("/anip/approval_grants")
            .then().statusCode(400);
    }

    @Test
    void zeroMaxUsesRejected() throws Exception {
        String id = persistRequest("apr_zeromu",
                new GrantPolicy(List.of("one_time"), "one_time", 600, 1));
        given().contentType("application/json")
            .header("Authorization", "Bearer " + approverJwt)
            .body("{\"approval_request_id\":\"" + id + "\",\"grant_type\":\"one_time\",\"max_uses\":0}")
            .when().post("/anip/approval_grants")
            .then().statusCode(400);
    }

    @Test
    void unknownApprovalRequestReturns404() {
        given().contentType("application/json")
            .header("Authorization", "Bearer " + approverJwt)
            .body("{\"approval_request_id\":\"apr_does_not_exist\",\"grant_type\":\"one_time\"}")
            .when().post("/anip/approval_grants")
            .then().statusCode(404)
            .body("failure.type", equalTo("approval_request_not_found"));
    }

    @Test
    void stateCheckBeforeApproverAuth() throws Exception {
        // Pre-decided request: state check should kick in BEFORE approver auth.
        // We use a token WITHOUT approver:* scope to prove state check runs first.
        TokenRequest noScopeReq = new TokenRequest(
                "agent:test", List.of("travel"), null,
                null, null, 0, null);
        String noApproverJwt = service.issueToken("user@test.com", noScopeReq).getToken();
        // Persist a request whose status is already approved.
        SqliteStorage storage = (SqliteStorage) service.getStorage();
        ApprovalRequest req = new ApprovalRequest(
                "apr_decided", "search_flights", List.of("travel"),
                Map.of("subject", "alice"), null,
                Map.of(), "p", Map.of(), "q",
                new GrantPolicy(List.of("one_time"), "one_time", 600, 1),
                ApprovalRequest.STATUS_APPROVED, null, null,
                V023.utcNowIso(), V023.utcInIso(900));
        storage.storeApprovalRequest(req);
        given().contentType("application/json")
            .header("Authorization", "Bearer " + noApproverJwt)
            .body("{\"approval_request_id\":\"apr_decided\",\"grant_type\":\"one_time\"}")
            .when().post("/anip/approval_grants")
            .then().statusCode(409)
            .body("failure.type", equalTo("approval_request_already_decided"));
    }

    @Test
    void notAuthorizedApproverReturns403() throws Exception {
        String id = persistRequest("apr_unauth",
                new GrantPolicy(List.of("one_time"), "one_time", 600, 1));
        // Token lacks approver:* scope.
        TokenRequest noScopeReq = new TokenRequest(
                "agent:test", List.of("travel"), null,
                null, null, 0, null);
        String noApproverJwt = service.issueToken("user@test.com", noScopeReq).getToken();
        given().contentType("application/json")
            .header("Authorization", "Bearer " + noApproverJwt)
            .body("{\"approval_request_id\":\"" + id + "\",\"grant_type\":\"one_time\"}")
            .when().post("/anip/approval_grants")
            .then().statusCode(403)
            .body("failure.type", equalTo("approver_not_authorized"));
    }

    @Test
    void happyPathReturnsBareSignedGrant() throws Exception {
        String id = persistRequest("apr_happy_e",
                new GrantPolicy(List.of("one_time"), "one_time", 600, 1));
        given().contentType("application/json")
            .header("Authorization", "Bearer " + approverJwt)
            .body("{\"approval_request_id\":\"" + id + "\",\"grant_type\":\"one_time\"}")
            .when().post("/anip/approval_grants")
            .then().statusCode(200)
            // SPEC.md §4.9: response IS the bare grant — no wrapper.
            .body("grant_id", startsWith("grant_"))
            .body("approval_request_id", equalTo(id))
            .body("grant_type", equalTo("one_time"))
            .body("capability", equalTo("search_flights"))
            .body("max_uses", equalTo(1))
            .body("use_count", equalTo(0))
            .body("signature", notNullValue());
    }

    @Test
    void sessionBoundHappyPath() throws Exception {
        String id = persistRequest("apr_sb_e",
                new GrantPolicy(List.of("session_bound"), "session_bound", 600, 3));
        given().contentType("application/json")
            .header("Authorization", "Bearer " + approverJwt)
            .body("{\"approval_request_id\":\"" + id + "\",\"grant_type\":\"session_bound\",\"session_id\":\"sess-1\"}")
            .when().post("/anip/approval_grants")
            .then().statusCode(200)
            .body("grant_type", equalTo("session_bound"))
            .body("session_id", equalTo("sess-1"));
    }
}
