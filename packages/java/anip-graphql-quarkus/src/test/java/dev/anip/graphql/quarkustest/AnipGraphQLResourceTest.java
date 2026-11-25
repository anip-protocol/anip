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

    // --- Parameter validation (SPEC.md §6.3) in the result body ---

    @Test
    void inputThatDeclaresOnMissingIsNotANonNullArgument() {
        // 'cabin' is required and declares resolution.on_missing: the schema
        // does not demand it, and the call reaches the handler without it.
        given()
            .header("Authorization", "Bearer valid-api-key")
            .contentType("application/json")
            .body("{\"query\":\"{ searchFlights(origin: \\\"SFO\\\", destination: \\\"LAX\\\") { success result } }\"}")
            .when().post("/graphql")
            .then().statusCode(200)
            .body("errors", nullValue())
            .body("data.searchFlights.success", equalTo(true));

        given().when().get("/schema.graphql")
            .then().statusCode(200)
            .body(containsString("cabin: String)"))
            .body(containsString("origin: String!"));
    }

    @Test
    void invalidParametersInResultBody() {
        // GraphQL's own schema refuses a missing non-null argument; a value of
        // the wrong JSON type for a JSON-typed argument reaches the service.
        given()
            .header("Authorization", "Bearer valid-api-key")
            .contentType("application/json")
            .body("{\"query\":\"mutation { bookFlight(flightId: \\\"FL-001\\\", options: \\\"window\\\") { success result failure { type detail retry resolution { action recoveryClass requires } } } }\"}")
            .when().post("/graphql")
            .then().statusCode(200)
            .body("data.bookFlight.success", equalTo(false))
            .body("data.bookFlight.result", nullValue())
            .body("data.bookFlight.failure.type", equalTo("invalid_parameters"))
            .body("data.bookFlight.failure.detail",
                    equalTo("book_flight has invalid input(s): 'options' must be object, got string"))
            .body("data.bookFlight.failure.retry", equalTo(false))
            .body("data.bookFlight.failure.resolution.action", equalTo("retry_now"))
            .body("data.bookFlight.failure.resolution.recoveryClass", equalTo("retry_now"))
            .body("data.bookFlight.failure.resolution.requires",
                    equalTo("parameters that match the capability's declared inputs"));
    }

    @Test
    void missingRequiredArgumentIsRefusedBeforeTheHandler() {
        given()
            .header("Authorization", "Bearer valid-api-key")
            .contentType("application/json")
            .body("{\"query\":\"mutation { bookFlight { success result } }\"}")
            .when().post("/graphql")
            .then().statusCode(200)
            .body("errors", not(empty()))
            .body("data.bookFlight", nullValue());
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
