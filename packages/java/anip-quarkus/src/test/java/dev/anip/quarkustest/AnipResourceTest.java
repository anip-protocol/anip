package dev.anip.quarkustest;

import dev.anip.core.TokenRequest;
import dev.anip.service.ANIPService;
import io.quarkus.test.junit.QuarkusTest;
import jakarta.inject.Inject;
import org.junit.jupiter.api.*;

import java.util.List;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

@QuarkusTest
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class AnipResourceTest {

    @Inject
    ANIPService service;

    private String validJwt;

    @BeforeAll
    void setUp() throws Exception {
        var req = new TokenRequest(
                "agent:test", List.of("travel"), "search_flights",
                null, null, 0, null);
        var resp = service.issueToken("user@test.com", req);
        validJwt = resp.getToken();
    }

    @Test @Order(1) void discoveryReturns200() {
        given().when().get("/.well-known/anip")
            .then().statusCode(200)
            .body("anip_discovery.protocol", startsWith("anip/"))
            .body("anip_discovery.compliance", equalTo("anip-compliant"));
    }

    @Test @Order(2) void jwksReturnsKeys() {
        given().when().get("/.well-known/jwks.json")
            .then().statusCode(200)
            .body("keys", not(empty()));
    }

    @Test @Order(3) void manifestHasSignature() {
        given().when().get("/anip/manifest")
            .then().statusCode(200)
            .header("X-ANIP-Signature", notNullValue());
    }

    @Test @Order(4) void tokenIssuanceSuccess() {
        given().contentType("application/json")
            .header("Authorization", "Bearer valid-api-key")
            .body("{\"subject\":\"agent:test\",\"scope\":[\"travel\"],\"capability\":\"search_flights\"}")
            .when().post("/anip/tokens")
            .then().statusCode(200)
            .body("token_id", notNullValue())
            .body("token", notNullValue());
    }

    @Test @Order(5) void tokenIssuanceMissingAuth() {
        given().contentType("application/json")
            .body("{\"subject\":\"agent:test\",\"scope\":[\"travel\"]}")
            .when().post("/anip/tokens")
            .then().statusCode(401);
    }

    @Test @Order(6) void invokeSuccess() {
        given().contentType("application/json")
            .header("Authorization", "Bearer " + validJwt)
            .body("{\"parameters\":{\"origin\":\"SEA\",\"destination\":\"SFO\"}}")
            .when().post("/anip/invoke/search_flights")
            .then().statusCode(200)
            .body("success", equalTo(true))
            .body("invocation_id", startsWith("inv-"));
    }

    @Test @Order(7) void invokeMissingAuth() {
        given().contentType("application/json")
            .body("{\"parameters\":{}}")
            .when().post("/anip/invoke/search_flights")
            .then().statusCode(401);
    }

    @Test @Order(8) void invokeUnknownCapability() {
        given().contentType("application/json")
            .header("Authorization", "Bearer " + validJwt)
            .body("{\"parameters\":{}}")
            .when().post("/anip/invoke/nonexistent")
            .then().statusCode(404);
    }

    @Test @Order(9) void healthReturnsStatus() {
        given().when().get("/-/health")
            .then().statusCode(200)
            .body("status", equalTo("healthy"));
    }
}
