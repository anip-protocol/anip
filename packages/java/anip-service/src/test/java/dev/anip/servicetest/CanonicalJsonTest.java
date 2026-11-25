package dev.anip.servicetest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import dev.anip.service.JsonRequestBody;
import dev.anip.service.V023;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * SPEC.md §4.7 "Canonical JSON and Digests": approval digests are computed
 * over RFC 8785 canonical JSON.
 */
class CanonicalJsonTest {

    /**
     * The shared vectors: each JSON text is parsed with the parser the HTTP
     * bindings use for request bodies ({@link JsonRequestBody}), so the test
     * covers parse and canonicalise, including how numbers are represented.
     */
    @Test
    void sharedRfc8785VectorsPass() throws Exception {
        Path fixturePath = Path.of("..", "..", "canonical-json-fixtures", "rfc8785-vectors.json");
        JsonNode fixture = new ObjectMapper().readTree(fixturePath.toFile());
        JsonNode vectors = fixture.get("vectors");
        assertTrue(vectors.size() >= 65, "expected the shared vectors, found " + vectors.size());

        List<String> mismatches = new ArrayList<>();
        for (JsonNode vector : vectors) {
            String name = vector.get("name").asText();
            String actual;
            String digest;
            try {
                Object value = JsonRequestBody.parseValue(
                        vector.get("input").asText().getBytes(StandardCharsets.UTF_8));
                actual = V023.canonicalJson(value);
                digest = V023.sha256Digest(value);
            } catch (Exception e) {
                mismatches.add(name + ": " + e);
                continue;
            }
            String actualHex = HexFormat.of().formatHex(actual.getBytes(StandardCharsets.UTF_8));
            if (!vector.get("canonical_utf8_hex").asText().equals(actualHex)) {
                mismatches.add(name + ": expected " + vector.get("canonical").asText()
                        + " but was " + actual);
            } else if (!vector.get("sha256").asText().equals(digest)) {
                mismatches.add(name + ": digest expected " + vector.get("sha256").asText()
                        + " but was " + digest);
            }
        }
        assertEquals(List.of(), mismatches);
    }

    @Test
    void everyNumberRepresentationOfTheSameValueIsTheSameText() {
        for (Object five : List.of(5, 5L, (short) 5, (byte) 5, 5.0, 5.0f,
                BigInteger.valueOf(5), new BigDecimal("5"), new BigDecimal("5.0"),
                new BigDecimal("5e0"), new BigDecimal("0.5e1"))) {
            assertEquals("5", V023.canonicalJson(five), five.getClass().getSimpleName());
        }
        assertEquals(V023.sha256Digest(Map.of("passengers", 5)),
                V023.sha256Digest(Map.of("passengers", 5.0)));
        assertEquals(V023.sha256Digest(Map.of("passengers", 5)),
                V023.sha256Digest(Map.of("passengers", new BigDecimal("5.00"))));
        assertTrue(!V023.sha256Digest(Map.of("passengers", 5))
                .equals(V023.sha256Digest(Map.of("passengers", 6))));
    }

    @Test
    void numbersAreIeee754Doubles() {
        assertEquals("9007199254740992", V023.canonicalJson(9007199254740993L));
        assertEquals("9007199254740992", V023.canonicalJson(new BigInteger("9007199254740993")));
        assertEquals("0.1", V023.canonicalJson(new BigDecimal("0.1000000000000000055511151231257827")));
        assertEquals("1e+21", V023.canonicalJson(new BigInteger("1000000000000000000000")));
        assertEquals("100000000000000000000", V023.canonicalJson(new BigDecimal("1e20")));
        assertEquals("0.000001", V023.canonicalJson(1e-6));
        assertEquals("1e-7", V023.canonicalJson(1e-7));
        assertEquals("5e-324", V023.canonicalJson(Double.MIN_VALUE));
        assertEquals("1.7976931348623157e+308", V023.canonicalJson(Double.MAX_VALUE));
        assertEquals("2.2250738585072014e-308", V023.canonicalJson(Double.MIN_NORMAL));
        assertEquals("0", V023.canonicalJson(-0.0));
        assertEquals("0.10000000149011612", V023.canonicalJson(0.1f));
        assertEquals("-1.5", V023.canonicalJson(-1.5));
    }

    @Test
    void nonFiniteNumbersAreAnError() {
        for (Object value : List.of(Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY,
                Float.NaN, new BigDecimal("1e400"))) {
            assertThrows(IllegalArgumentException.class, () -> V023.canonicalJson(Map.of("n", value)),
                    String.valueOf(value));
        }
    }

    /** The digits written for a double read back as the same double. */
    @Test
    void writtenNumbersRoundTrip() {
        Random random = new Random(8785);
        List<Double> values = new ArrayList<>();
        for (int k = 0; k < 20000; k++) {
            double d = Double.longBitsToDouble(random.nextLong());
            if (!Double.isNaN(d) && !Double.isInfinite(d)) values.add(d);
        }
        // Powers of two, where the gap to the lower neighbour is half the gap above.
        for (int exponent = -1074; exponent <= 1023; exponent++) {
            double power = Math.scalb(1.0, exponent);
            values.add(power);
            values.add(Math.nextDown(power));
            values.add(Math.nextUp(power));
        }
        for (double d : values) {
            String text = V023.canonicalJson(d);
            assertEquals(d == 0 ? 0.0 : d, Double.parseDouble(text), text);
            // Never longer than the 17 significant digits that identify any double.
            String digits = text.replaceAll("e.*$", "").replaceAll("[-.]", "").replaceAll("^0+", "");
            assertTrue(digits.replaceAll("0+$", "").length() <= 17, text);
        }
    }

    @Test
    void stringsEscapeOnlyWhatRfc8785Requires() {
        assertEquals("\"\\u0000\\u001f\\b\\t\\n\\f\\r\\\"\\\\\"",
                V023.canonicalJson("\u0000\u001f\b\t\n\f\r\"\\"));
        assertEquals("\"/<>&'\u007f  é😀\"",
                V023.canonicalJson("/<>&'\u007f  é😀"));
    }

    @Test
    void keysAreSortedByUtf16CodeUnits() {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("￿", 1);
        value.put("𐀀", 2);   // U+10000: its first code unit sorts before U+E000
        value.put("", 3);
        value.put("b", 4);
        value.put("a", Map.of("z", List.of(true, false), "y", "x"));
        assertEquals("{\"a\":{\"y\":\"x\",\"z\":[true,false]},\"b\":4,"
                + "\"𐀀\":2,\"\":3,\"￿\":1}", V023.canonicalJson(value));
    }

    @Test
    void nullsArraysAndNestedValues() {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("n", null);
        value.put("a", new Object[] {1, "x", null});
        value.put("l", List.of());
        value.put("o", Map.of());
        assertEquals("{\"a\":[1,\"x\",null],\"l\":[],\"n\":null,\"o\":{}}", V023.canonicalJson(value));
        assertEquals("null", V023.canonicalJson(null));
    }

    @Test
    void jacksonTreesAndPojosAreCanonicalisedAsTheirJson() throws Exception {
        JsonNode tree = new ObjectMapper().readTree("{\"b\":1.0,\"a\":[1e2,{\"d\":null,\"c\":\"x\"}]}");
        assertEquals("{\"a\":[100,{\"c\":\"x\",\"d\":null}],\"b\":1}", V023.canonicalJson(tree));

        record Point(int xCoordinate, double y) { }
        assertEquals("{\"x_coordinate\":1,\"y\":2.5}", V023.canonicalJson(new Point(1, 2.5)));
    }
}
