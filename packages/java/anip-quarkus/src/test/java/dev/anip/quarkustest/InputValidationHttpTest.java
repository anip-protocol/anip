package dev.anip.quarkustest;

import dev.anip.core.TokenRequest;
import dev.anip.service.ANIPService;

import io.quarkus.test.junit.QuarkusTest;
import io.restassured.response.ValidatableResponse;
import jakarta.inject.Inject;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;

import java.util.List;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.emptyOrNullString;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.nullValue;
import static org.hamcrest.Matchers.startsWith;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * SPEC.md §6.3 "Parameter Validation" and "HTTP Status Codes" on the Quarkus
 * binding. The Spring Boot binding runs the same cases
 * ({@code dev.anip.springtest.InputValidationHttpTest}).
 */
@QuarkusTest
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class InputValidationHttpTest {

    private static final String REQUIRES = "parameters that match the capability's declared inputs";

    @Inject
    ANIPService service;

    private String searchJwt;
    private String bookJwt;

    @BeforeAll
    void setUp() throws Exception {
        searchJwt = service.issueToken("user@test.com", new TokenRequest(
                "agent:test", List.of("travel", "finance"), "search_flights",
                null, null, 0, null)).getToken();
        bookJwt = service.issueToken("user@test.com", new TokenRequest(
                "agent:test", List.of("travel", "finance"), "book_flight",
                null, null, 0, null)).getToken();
    }

    private ValidatableResponse invoke(String capability, String jwt, String body) {
        var request = given().contentType("application/json").body(body);
        if (jwt != null) {
            request = request.header("Authorization", "Bearer " + jwt);
        }
        return request.when().post("/anip/invoke/" + capability).then();
    }

    private static ValidatableResponse expectInvalidParameters(ValidatableResponse response, String detail) {
        return response
                .statusCode(400)
                .body("success", equalTo(false))
                .body("result", nullValue())
                .body("failure.type", equalTo("invalid_parameters"))
                .body("failure.detail", equalTo(detail))
                .body("failure.resolution.action", equalTo("retry_now"))
                .body("failure.resolution.recovery_class", equalTo("retry_now"))
                .body("failure.resolution.requires", equalTo(REQUIRES))
                .body("failure.retry", equalTo(false))
                .body("invocation_id", startsWith("inv-"));
    }

    // --- parameter validation, unary ---

    @Test
    void missingRequiredInputIs400InvalidParameters() {
        expectInvalidParameters(
                invoke("search_flights", searchJwt, "{\"parameters\":{\"origin\":\"SEA\"}}"),
                "search_flights is missing required input(s): destination");
    }

    @Test
    void emptyBodyHasNoParameters() {
        expectInvalidParameters(
                invoke("search_flights", searchJwt, "{}"),
                "search_flights is missing required input(s): origin, destination");
    }

    @Test
    void nullForARequiredInputIs400InvalidParameters() {
        expectInvalidParameters(
                invoke("search_flights", searchJwt,
                        "{\"parameters\":{\"origin\":null,\"destination\":\"SFO\"}}"),
                "search_flights is missing required input(s): origin");
    }

    @Test
    void wrongTypeIs400InvalidParameters() {
        expectInvalidParameters(
                invoke("search_flights", searchJwt,
                        "{\"parameters\":{\"origin\":5,\"destination\":[\"SFO\"]}}"),
                "search_flights has invalid input(s): 'origin' must be string, got number; "
                        + "'destination' must be string, got array");
    }

    @Test
    void undeclaredParametersAre400InvalidParameters() {
        expectInvalidParameters(
                invoke("search_flights", searchJwt,
                        "{\"parameters\":{\"origin\":\"SEA\",\"destination\":\"SFO\",\"extra\":[1],\"also\":null}}"),
                "search_flights has undeclared parameter(s): also, extra");
    }

    @Test
    void validParametersStillSucceed() {
        invoke("search_flights", searchJwt,
                "{\"parameters\":{\"origin\":\"SEA\",\"destination\":\"SFO\"}}")
                .statusCode(200)
                .body("success", equalTo(true));
    }

    // --- parameter validation, streaming ---

    /** The body of an SSE response, with the spaces after field names removed. */
    private String sse(ValidatableResponse response) {
        return response.statusCode(200).extract().asString()
                .replace("event: ", "event:").replace("data: ", "data:");
    }

    @Test
    void streamingInvocationIsRefusedWithTheSameFailure() {
        String body = sse(invoke("search_flights", searchJwt,
                "{\"parameters\":{\"origin\":\"SEA\"},\"stream\":true}"));

        assertTrue(body.contains("event:failed"), body);
        assertTrue(body.contains("\"type\":\"invalid_parameters\""), body);
        assertTrue(body.contains(
                "\"detail\":\"search_flights is missing required input(s): destination\""), body);
        assertTrue(body.contains("\"action\":\"retry_now\""), body);
        assertTrue(body.contains("\"recovery_class\":\"retry_now\""), body);
        assertTrue(body.contains("\"requires\":\"" + REQUIRES + "\""), body);
        assertTrue(body.contains("\"retry\":false"), body);
        assertTrue(body.contains("\"invocation_id\":\"inv-"), body);
        assertTrue(!body.contains("event:completed"), body);
    }

    // --- the streaming path runs the unary pre-handler checks ---

    @Test
    void streamingInvocationWithoutItsBindingIsRefusedBeforeTheHandler() throws Exception {
        String holdJwt = service.issueToken("user@test.com", new TokenRequest(
                "agent:test", List.of("travel"), "hold_seat", null, null, 0, null)).getToken();
        String body = sse(invoke("hold_seat", holdJwt, "{\"parameters\":{},\"stream\":true}"));

        assertTrue(body.contains("event:failed"), body);
        assertTrue(body.contains("\"type\":\"binding_missing\""), body);
        assertTrue(body.contains("\"action\":\"obtain_binding\""), body);
        assertTrue(body.contains("\"invocation_id\":\"inv-"), body);
        assertTrue(!body.contains("event:completed"), body);

        // The same request, unary.
        invoke("hold_seat", holdJwt, "{\"parameters\":{}}")
                .statusCode(403)
                .body("failure.type", equalTo("binding_missing"));
    }

    @Test
    void streamingInvocationWithATokenForAnotherCapabilityCarriesTheUnaryFailure() {
        String body = sse(invoke("search_flights", bookJwt,
                "{\"parameters\":{\"origin\":\"SEA\",\"destination\":\"SFO\"},\"stream\":true}"));

        assertTrue(body.contains("event:failed"), body);
        assertTrue(body.contains("\"type\":\"purpose_mismatch\""), body);
        assertTrue(body.contains("\"resolution\":{\"action\":"), body);
        assertTrue(body.contains("\"retry\":false"), body);
        assertTrue(!body.contains("event:completed"), body);
    }

    @Test
    void streamingInvocationWithAnUnknownGrantCarriesTheUnaryFailure() {
        for (String grant : List.of("", "grant_0123456789ab")) {
            String body = sse(invoke("search_flights", searchJwt,
                    "{\"parameters\":{\"origin\":\"SEA\",\"destination\":\"SFO\"},"
                            + "\"approval_grant\":\"" + grant + "\",\"stream\":true}"));

            assertTrue(body.contains("event:failed"), body);
            assertTrue(body.contains("\"type\":\"grant_not_found\""), body);
            assertTrue(body.contains("\"action\":\"contact_service_owner\""), body);
            assertTrue(!body.contains("event:completed"), body);
        }
    }

    @Test
    void streamingInvocationWithValidParametersCompletes() {
        String body = sse(invoke("search_flights", searchJwt,
                "{\"parameters\":{\"origin\":\"SEA\",\"destination\":\"SFO\"},\"stream\":true}"));
        assertTrue(body.contains("event:completed"), body);
    }

    // --- a request body that is not JSON (SPEC.md §6.3, HTTP Status Codes) ---

    private static ValidatableResponse expectBodyRefused(ValidatableResponse response) {
        return response
                .statusCode(400)
                .body("success", equalTo(false))
                .body("failure.type", equalTo("invalid_parameters"))
                .body("failure.detail", not(emptyOrNullString()))
                .body("failure.resolution.action", equalTo("retry_now"))
                .body("failure.resolution.recovery_class", equalTo("retry_now"))
                .body("failure.retry", equalTo(false));
    }

    @Test
    void invokeBodyThatIsNotJsonIs400InvalidParameters() {
        expectBodyRefused(invoke("search_flights", searchJwt, "{\"parameters\": "));
    }

    @Test
    void invokeBodyThatIsNotAnObjectIs400InvalidParameters() {
        expectBodyRefused(invoke("search_flights", searchJwt, "[\"SEA\"]"));
        expectBodyRefused(invoke("search_flights", searchJwt, "{\"parameters\":[\"SEA\"]}"));
    }

    @Test
    void parametersThatAreNotAnObjectAreRefusedWithTheSpecifiedDetail() {
        // SPEC.md §6.3: "<capability> parameters must be an object, got <JSON type>".
        String[][] cases = {
                {"[\"SEA\"]", "array"}, {"\"SEA\"", "string"}, {"1.5", "number"}, {"true", "boolean"}};
        for (String[] c : cases) {
            expectBodyRefused(invoke("search_flights", searchJwt, "{\"parameters\":" + c[0] + "}"))
                    .body("failure.detail",
                            equalTo("search_flights parameters must be an object, got " + c[1]))
                    .body("failure.resolution.requires", equalTo(REQUIRES));
        }
    }

    @Test
    void invokeBodyThatIsNotJsonWithoutCredentialIs401() {
        invoke("search_flights", null, "{\"parameters\": ")
                .statusCode(401)
                .body("failure.type", equalTo("authentication_required"));
        invoke("search_flights", "not-a-token", "{\"parameters\": ")
                .statusCode(401)
                .body("failure.type", equalTo("invalid_token"));
    }

    private ValidatableResponse tokens(String bearer, String body) {
        var request = given().contentType("application/json").body(body);
        if (bearer != null) {
            request = request.header("Authorization", "Bearer " + bearer);
        }
        return request.when().post("/anip/tokens").then();
    }

    @Test
    void tokenRequestBodyThatIsNotJsonIs400InvalidParameters() {
        expectBodyRefused(tokens("valid-api-key", "{\"scope\": "));
        expectBodyRefused(tokens("valid-api-key", "[]"));
        expectBodyRefused(tokens("valid-api-key", ""));
    }

    @Test
    void tokenRequestBodyThatIsNotJsonWithoutCredentialIs401() {
        tokens(null, "{\"scope\": ")
                .statusCode(401)
                .body("failure.type", equalTo("authentication_required"));
        tokens("bad-key", "{\"scope\": ")
                .statusCode(401)
                .body("failure.type", equalTo("authentication_required"));
    }

    @Test
    void wellFormedTokenRequestStillIssues() {
        tokens("valid-api-key",
                "{\"subject\":\"agent\",\"scope\":[\"travel\"],\"capability\":\"search_flights\"}")
                .statusCode(200)
                .body("issued", equalTo(true));
    }

    // --- stream: true on a capability that only supports unary ---

    @Test
    void streamingRequestedFromAUnaryCapabilityIsAJsonFailure() {
        invoke("book_flight", bookJwt, "{\"parameters\":{\"flight_id\":\"FL-001\"},\"stream\":true}")
                .statusCode(400)
                .contentType(containsString("application/json"))
                .body("success", equalTo(false))
                .body("failure.type", equalTo("streaming_not_supported"))
                .body("failure.detail", not(emptyOrNullString()))
                .body("failure.resolution.action", equalTo("check_manifest"))
                .body("failure.resolution.recovery_class", equalTo("revalidate_then_retry"))
                .body("failure.retry", equalTo(false));
    }
}
