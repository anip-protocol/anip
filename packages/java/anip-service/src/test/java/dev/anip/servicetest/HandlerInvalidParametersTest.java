package dev.anip.servicetest;

import dev.anip.core.ANIPError;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.Constants;
import dev.anip.core.DelegationToken;
import dev.anip.core.SideEffect;
import dev.anip.core.TokenRequest;
import dev.anip.service.ANIPService;
import dev.anip.service.CapabilityDef;
import dev.anip.service.InvokeOpts;
import dev.anip.service.ServiceConfig;
import dev.anip.service.StreamEvent;
import dev.anip.service.StreamResult;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * A handler validates what the runtime does not (a domain type, a value
 * range). When it raises {@code invalid_parameters} without a resolution the
 * failure is the runtime's own: the retry_now resolution with the same
 * {@code requires} text, and {@code retry} stated and false.
 */
class HandlerInvalidParametersTest {

    private ANIPService service;

    private static CapabilityDeclaration declaration(String name) {
        return new CapabilityDeclaration(name, name, "1.0",
                List.of(new CapabilityInput("date", "date", true, "Travel date")),
                new CapabilityOutput("object", List.of()),
                new SideEffect("read", "not_applicable"),
                List.of("travel.search"), null, null, List.of("unary", "streaming"));
    }

    @BeforeEach
    void setUp() throws Exception {
        service = new ANIPService(new ServiceConfig()
                .setServiceId("handler-invalid-test")
                .setStorage(":memory:")
                .setCapabilities(List.of(
                        new CapabilityDef(declaration("check_date"), (ctx, params) -> {
                            throw new ANIPError(Constants.FAILURE_INVALID_PARAMETERS, "date must be YYYY-MM-DD");
                        }),
                        new CapabilityDef(declaration("reload"), (ctx, params) -> {
                            throw new ANIPError(Constants.FAILURE_INVALID_PARAMETERS,
                                    "the fare table is being reloaded")
                                    .withResolution("wait_and_retry").withRetry();
                        })))
                .setAuthenticate(b -> "valid".equals(b) ? Optional.of("alice") : Optional.empty())
                .setRetentionIntervalSeconds(-1));
        service.start();
    }

    @AfterEach
    void tearDown() {
        if (service != null) service.shutdown();
    }

    private DelegationToken token(String capability) throws Exception {
        return service.resolveBearerToken(service.issueToken("alice", new TokenRequest(
                "agent", List.of("travel.search"), capability, null, null, 1, null)).getToken());
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> unaryFailure(String capability) throws Exception {
        Map<String, Object> response = service.invoke(capability, token(capability),
                Map.of("date", "tomorrow"), new InvokeOpts());
        assertEquals(false, response.get("success"));
        return (Map<String, Object>) response.get("failure");
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> streamedFailure(String capability) throws Exception {
        StreamResult result = service.invokeStream(capability, token(capability),
                Map.of("date", "tomorrow"), new InvokeOpts());
        StreamEvent last = null;
        while (true) {
            StreamEvent event = result.getEvents().poll(5, TimeUnit.SECONDS);
            assertNotNull(event, "timed out waiting for a stream event");
            if (StreamResult.DONE_TYPE.equals(event.getType())) break;
            last = event;
        }
        assertEquals("failed", last.getType());
        return (Map<String, Object>) last.getPayload().get("failure");
    }

    private static void assertRuntimeFailure(Map<String, Object> failure) {
        assertEquals(Constants.FAILURE_INVALID_PARAMETERS, failure.get("type"));
        assertEquals("date must be YYYY-MM-DD", failure.get("detail"));
        assertEquals(Map.of(
                "action", "retry_now",
                "recovery_class", "retry_now",
                "requires", "parameters that match the capability's declared inputs"),
                failure.get("resolution"));
        assertTrue(failure.containsKey("retry"), "retry must be stated: " + failure);
        assertEquals(false, failure.get("retry"));
    }

    @Test
    void handlerRaisedInvalidParametersGetsTheRuntimeResolution() throws Exception {
        assertRuntimeFailure(unaryFailure("check_date"));
    }

    @Test
    void handlerRaisedInvalidParametersGetsTheRuntimeResolutionOnAStream() throws Exception {
        assertRuntimeFailure(streamedFailure("check_date"));
    }

    @Test
    void aHandlerThatNamesItsOwnResolutionAndRetryKeepsThem() throws Exception {
        for (Map<String, Object> failure : List.of(unaryFailure("reload"), streamedFailure("reload"))) {
            assertEquals(Constants.FAILURE_INVALID_PARAMETERS, failure.get("type"));
            assertEquals("the fare table is being reloaded", failure.get("detail"));
            assertEquals(Map.of("action", "wait_and_retry", "recovery_class", "wait_then_retry"),
                    failure.get("resolution"));
            assertEquals(true, failure.get("retry"));
        }
    }
}
