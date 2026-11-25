package dev.anip.service;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.ObjectReader;

import dev.anip.core.ANIPError;
import dev.anip.core.Constants;
import dev.anip.core.Resolution;

import java.io.IOException;
import java.util.Map;

/**
 * Reads the JSON body of an HTTP request. Every HTTP binding (the protocol
 * endpoints and the REST adapter) reads request bodies through this class, so
 * that a body that is not JSON is the same {@code invalid_parameters} failure
 * everywhere (SPEC.md §6.3, HTTP Status Codes) instead of a framework error
 * page, and so that numbers reach the service in one representation:
 * {@code Integer}, {@code Long} or {@code BigInteger} for an integer literal,
 * {@code Double} for any other number.
 */
public final class JsonRequestBody {

    private static final ObjectReader READER = new ObjectMapper()
            .readerFor(Object.class)
            .with(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);

    private JsonRequestBody() {}

    /**
     * Parses a JSON text into maps, lists, strings, numbers, booleans and
     * {@code null}.
     *
     * @throws IOException when the text is not one JSON value
     */
    public static Object parseValue(byte[] json) throws IOException {
        return READER.readValue(json);
    }

    /**
     * Reads a request body that, when present, must be a JSON object.
     *
     * @return the object, or {@code null} when the body is absent or empty
     * @throws ANIPError {@code invalid_parameters} when the body is not JSON
     *                   or is not a JSON object
     */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> readObject(byte[] body) {
        if (isEmpty(body)) {
            return null;
        }
        Object value;
        try {
            value = parseValue(body);
        } catch (IOException e) {
            throw invalid("request body must be JSON");
        }
        if (!(value instanceof Map<?, ?>)) {
            throw invalid("request body must be a JSON object");
        }
        return (Map<String, Object>) value;
    }

    /**
     * Reads a request body that must be a JSON object.
     *
     * @throws ANIPError {@code invalid_parameters} when the body is absent,
     *                   is not JSON or is not a JSON object
     */
    public static Map<String, Object> requireObject(byte[] body) {
        Map<String, Object> value = readObject(body);
        if (value == null) {
            throw invalid("request body must be a JSON object");
        }
        return value;
    }

    /**
     * The {@code parameters} member of an invocation body: {@code null} when
     * the body is absent, has no such member, or the member is {@code null}
     * (SPEC.md §6.3: absent or null parameters are the empty object).
     *
     * @param capability the invoked capability, named in the failure detail
     * @throws ANIPError {@code invalid_parameters} when the member is present
     *                   and is neither an object nor {@code null}: it does not
     *                   match the request schema
     */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> parametersOf(String capability, Map<String, Object> body) {
        Object parameters = body != null ? body.get("parameters") : null;
        if (parameters == null) {
            return null;
        }
        if (!(parameters instanceof Map<?, ?>)) {
            throw new ANIPError(Constants.FAILURE_INVALID_PARAMETERS,
                    capability + " parameters must be an object, got "
                            + ParameterValidation.jsonType(parameters))
                    .withResolution(new Resolution("retry_now",
                            Constants.recoveryClassForAction("retry_now"),
                            ParameterValidation.REQUIRES, null, null));
        }
        return (Map<String, Object>) parameters;
    }

    private static boolean isEmpty(byte[] body) {
        if (body == null) {
            return true;
        }
        for (byte b : body) {
            if (b != ' ' && b != '\t' && b != '\n' && b != '\r') {
                return false;
            }
        }
        return true;
    }

    private static ANIPError invalid(String detail) {
        return new ANIPError(Constants.FAILURE_INVALID_PARAMETERS, detail).withResolution("retry_now");
    }
}
