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
