package dev.anip.graphql.quarkustest;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

@QuarkusTest
class AnipGraphQLResourceTest {

    // --- Query execution with API key ---

    @Test
    void queryWithApiKeyReturnsData() {
        given()
            .header("Authorization", "Bearer valid-api-key")
            .contentType("application/json")
            .body("{\"query\":\"{ searchFlights(origin: \\\"SFO\\\", destination: \\\"LAX\\\") { success result } }\"}")
            .when().post("/graphql")
            .then().statusCode(200)
            .body("data.searchFlights.success", equalTo(true))
            .body("data.searchFlights.result", notNullValue());
    }

    // --- Auth errors in result body (not HTTP 401) ---

    @Test
    void queryWithoutAuthReturnsErrorInBody() {
        given()
            .contentType("application/json")
            .body("{\"query\":\"{ searchFlights(origin: \\\"SFO\\\", destination: \\\"LAX\\\") { success failure { type detail retry } } }\"}")
            .when().post("/graphql")
            .then().statusCode(200)
            .body("data.searchFlights.success", equalTo(false))
            .body("data.searchFlights.failure.type", equalTo("authentication_required"));
    }

    // --- SDL endpoint ---

    @Test
    void schemaEndpointReturnsSdl() {
        given()
            .when().get("/schema.graphql")
            .then().statusCode(200)
            .contentType(containsString("text/plain"))
            .body(containsString("type Query"))
            .body(containsString("searchFlights"))
            .body(containsString("@anipSideEffect"));
    }

    // --- Playground ---

    @Test
    void playgroundReturnsHtml() {
        given()
            .accept("text/html")
            .when().get("/graphql")
            .then().statusCode(200)
            .contentType(containsString("text/html"))
            .body(containsString("ANIP GraphQL"));
    }
}
