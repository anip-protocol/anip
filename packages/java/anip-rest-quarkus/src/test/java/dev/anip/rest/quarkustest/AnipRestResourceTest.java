package dev.anip.rest.quarkustest;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

@QuarkusTest
class AnipRestResourceTest {

    // --- OpenAPI ---

    @Test
    void openApiReturns200WithSpec() {
        given().when().get("/rest/openapi.json")
            .then().statusCode(200)
            .body("openapi", equalTo("3.1.0"))
            .body("paths", notNullValue())
            .body("components", notNullValue());
    }

    // --- GET (read capability) ---

    @Test
    void getReadCapabilityReturns200() {
        given()
            .header("Authorization", "Bearer valid-api-key")
            .queryParam("q", "test")
            .when().get("/api/search_flights")
            .then().statusCode(200)
            .body("success", equalTo(true))
            .body("result.flights", not(empty()));
    }

    // --- POST (write capability) ---

    @Test
    void postWriteCapabilityReturns200() {
        given()
            .header("Authorization", "Bearer valid-api-key")
            .contentType("application/json")
            .body("{\"name\":\"Widget\"}")
            .when().post("/api/create_item")
            .then().statusCode(200)
            .body("success", equalTo(true))
            .body("result.item_id", equalTo("ITEM-001"));
    }

    // --- Parameter validation (SPEC.md §6.3) ---

    @Test
    void inputThatDeclaresOnMissingIsNotDemandedOfTheCaller() {
        // 'cabin' is required and declares resolution.on_missing.
        given()
            .header("Authorization", "Bearer valid-api-key")
            .queryParam("q", "test")
            .when().get("/api/search_flights")
            .then().statusCode(200)
            .body("success", equalTo(true));
        given().when().get("/rest/openapi.json")
            .then().statusCode(200)
            .body("paths.'/api/search_flights'.get.parameters.find { it.name == 'cabin' }.required",
                    equalTo(false))
            .body("paths.'/api/search_flights'.get.parameters.find { it.name == 'q' }.required",
                    equalTo(true));
    }

    @Test
    void getMissingRequiredInputIsInvalidParameters() {
        given()
            .header("Authorization", "Bearer valid-api-key")
            .when().get("/api/search_flights")
            .then().statusCode(400)
            .body("success", equalTo(false))
            .body("failure.type", equalTo("invalid_parameters"))
            .body("failure.detail", equalTo("search_flights is missing required input(s): q"))
            .body("failure.resolution.action", equalTo("retry_now"))
            .body("failure.resolution.recovery_class", equalTo("retry_now"))
            .body("failure.resolution.requires",
                    equalTo("parameters that match the capability's declared inputs"))
            .body("failure.retry", equalTo(false))
            .body("invocation_id", notNullValue());
    }

    @Test
    void postMissingRequiredInputIsInvalidParameters() {
        given()
            .header("Authorization", "Bearer valid-api-key")
            .contentType("application/json")
            .body("{}")
            .when().post("/api/create_item")
            .then().statusCode(400)
            .body("failure.type", equalTo("invalid_parameters"))
            .body("failure.detail", equalTo("create_item is missing required input(s): name"))
            .body("failure.resolution.action", equalTo("retry_now"))
            .body("failure.retry", equalTo(false));
    }

    @Test
    void postWrongTypeIsInvalidParameters() {
        given()
            .header("Authorization", "Bearer valid-api-key")
            .contentType("application/json")
            .body("{\"name\":[\"Widget\"]}")
            .when().post("/api/create_item")
            .then().statusCode(400)
            .body("failure.type", equalTo("invalid_parameters"))
            .body("failure.detail",
                    equalTo("create_item has invalid input(s): 'name' must be string, got array"));
    }

    // --- A request body that is not JSON (SPEC.md §6.3, HTTP Status Codes) ---

    @Test
    void postBodyThatIsNotJsonIsInvalidParameters() {
        for (String body : java.util.List.of("{\"name\": ", "[\"Widget\"]", "{\"parameters\":7}")) {
            given()
                .header("Authorization", "Bearer valid-api-key")
                .contentType("application/json")
                .body(body)
                .when().post("/api/create_item")
                .then().statusCode(400)
                .body("success", equalTo(false))
                .body("failure.type", equalTo("invalid_parameters"))
                .body("failure.resolution.action", equalTo("retry_now"))
                .body("failure.resolution.recovery_class", equalTo("retry_now"))
                .body("failure.retry", equalTo(false));
        }
    }

    @Test
    void postBodyThatIsNotJsonWithoutCredentialIs401() {
        given()
            .contentType("application/json")
            .body("{\"name\": ")
            .when().post("/api/create_item")
            .then().statusCode(401)
            .body("failure.type", equalTo("authentication_required"));
    }

    // --- Missing auth ---

    @Test
    void missingAuthReturns401() {
        given()
            .when().get("/api/search_flights")
            .then().statusCode(401)
            .body("success", equalTo(false))
            .body("failure.type", equalTo("authentication_required"));
    }

    // --- Unknown capability ---

    @Test
    void unknownCapabilityReturns404() {
        given()
            .header("Authorization", "Bearer valid-api-key")
            .when().get("/api/nonexistent")
            .then().statusCode(404)
            .body("success", equalTo(false))
            .body("failure.type", equalTo("unknown_capability"));
    }
}
