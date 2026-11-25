package dev.anip.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fasterxml.jackson.module.paramnames.ParameterNamesModule;

import dev.anip.server.AnipJacksonModule;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.MathContext;
import java.math.RoundingMode;
import java.util.Map;
import java.util.TreeMap;

/**
 * The JSON Canonicalization Scheme, RFC 8785, as SPEC.md §4.7 requires for
 * approval digests.
 *
 * <ul>
 *   <li>object members sorted by the UTF-16 code units of their names;</li>
 *   <li>no insignificant whitespace;</li>
 *   <li>strings escaped as RFC 8785 §3.2.2.2: only {@code "}, {@code \} and
 *       the characters below U+0020 are escaped;</li>
 *   <li>every number converted to an IEEE 754 double and written as
 *       ECMAScript's {@code Number.prototype.toString} writes it.</li>
 * </ul>
 *
 * <p>The digits of a number are derived here from the exact value of the
 * double, not from {@link Double#toString(double)}, whose output differs
 * between JDK versions and is not always the shortest representation.</p>
 */
final class CanonicalJson {

    private CanonicalJson() {}

    /** Converts a value that is not a plain JSON tree (a POJO, a record) into one. */
    private static final ObjectMapper MAPPER = JsonMapper.builder()
            .addModule(new ParameterNamesModule())
            .addModule(new AnipJacksonModule())
            .propertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
            .configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false)
            .build();

    private static final char[] HEX = "0123456789abcdef".toCharArray();

    static String canonicalize(Object value) {
        StringBuilder sb = new StringBuilder();
        write(sb, value);
        return sb.toString();
    }

    private static void write(StringBuilder sb, Object v) {
        if (v == null) {
            sb.append("null");
        } else if (v instanceof Boolean b) {
            sb.append(b ? "true" : "false");
        } else if (v instanceof Number n) {
            sb.append(number(toDouble(n)));
        } else if (v instanceof CharSequence || v instanceof Character) {
            writeString(sb, v.toString());
        } else if (v instanceof Map<?, ?> map) {
            // String.compareTo orders by UTF-16 code units, as RFC 8785 §3.2.3 requires.
            TreeMap<String, Object> sorted = new TreeMap<>();
            for (Map.Entry<?, ?> e : map.entrySet()) {
                sorted.put(String.valueOf(e.getKey()), e.getValue());
            }
            sb.append('{');
            boolean first = true;
            for (Map.Entry<String, Object> e : sorted.entrySet()) {
                if (!first) sb.append(',');
                first = false;
                writeString(sb, e.getKey());
                sb.append(':');
                write(sb, e.getValue());
            }
            sb.append('}');
        } else if (v instanceof Iterable<?> items && !(v instanceof JsonNode)) {
            sb.append('[');
            boolean first = true;
            for (Object item : items) {
                if (!first) sb.append(',');
                first = false;
                write(sb, item);
            }
            sb.append(']');
        } else if (v instanceof Object[] items) {
            write(sb, java.util.Arrays.asList(items));
        } else {
            // A Jackson tree, a POJO, a record, an enum, a primitive array:
            // reduce it to maps, lists and scalars first.
            Object tree = MAPPER.convertValue(v, Object.class);
            if (tree != null && tree.getClass() == v.getClass()
                    && !(tree instanceof Map) && !(tree instanceof Iterable)
                    && !(tree instanceof CharSequence) && !(tree instanceof Number)
                    && !(tree instanceof Boolean)) {
                throw new IllegalArgumentException(
                        "canonical JSON: unsupported value of type " + v.getClass().getName());
            }
            write(sb, tree);
        }
    }

    /** RFC 8785 §3.2.2.2. */
    private static void writeString(StringBuilder sb, String s) {
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"' -> sb.append("\\\"");
                case '\\' -> sb.append("\\\\");
                case '\b' -> sb.append("\\b");
                case '\t' -> sb.append("\\t");
                case '\n' -> sb.append("\\n");
                case '\f' -> sb.append("\\f");
                case '\r' -> sb.append("\\r");
                default -> {
                    if (c < 0x20) {
                        sb.append("\\u00").append(HEX[c >> 4]).append(HEX[c & 0xf]);
                    } else {
                        sb.append(c);
                    }
                }
            }
        }
        sb.append('"');
    }

    /**
     * The IEEE 754 double nearest to a number in any representation a JSON
     * parser or a caller hands over (round to nearest, ties to even).
     */
    static double toDouble(Number n) {
        if (n instanceof Double d) return d;
        if (n instanceof Float f) return f.doubleValue();
        if (n instanceof Integer || n instanceof Long || n instanceof Short || n instanceof Byte) {
            return (double) n.longValue();
        }
        if (n instanceof BigInteger || n instanceof BigDecimal) {
            // Decimal text to double is correctly rounded by Double.parseDouble.
            return Double.parseDouble(n.toString());
        }
        return n.doubleValue();
    }

    /**
     * ECMAScript {@code Number.prototype.toString} (ECMA-262, Number::toString)
     * for a finite double: the shortest digits that round-trip, the candidate
     * closest to the value when there are several, plain notation for
     * 1e-6 &lt;= |x| &lt; 1e21 and exponent notation otherwise. {@code -0} is
     * {@code 0}.
     *
     * @throws IllegalArgumentException for NaN and the infinities
     */
    static String number(double x) {
        if (Double.isNaN(x) || Double.isInfinite(x)) {
            throw new IllegalArgumentException("canonical JSON: " + x + " is not a JSON number");
        }
        if (x == 0) {
            return "0";
        }
        if (x < 0) {
            return "-" + number(-x);
        }

        BigDecimal shortest = shortestDecimal(x).stripTrailingZeros();
        String digits = shortest.unscaledValue().toString();
        int k = digits.length();
        // value = digits x 10^(n - k)
        int n = k - shortest.scale();

        StringBuilder sb = new StringBuilder();
        if (k <= n && n <= 21) {
            sb.append(digits);
            sb.append("0".repeat(n - k));
        } else if (0 < n && n <= 21) {
            sb.append(digits, 0, n).append('.').append(digits, n, k);
        } else if (-6 < n && n <= 0) {
            sb.append("0.").append("0".repeat(-n)).append(digits);
        } else {
            int e = n - 1;
            sb.append(digits.charAt(0));
            if (k > 1) {
                sb.append('.').append(digits, 1, k);
            }
            sb.append('e').append(e < 0 ? '-' : '+').append(Math.abs(e));
        }
        return sb.toString();
    }

    /**
     * The decimal with the fewest significant digits that converts back to
     * {@code x} (positive, finite); of several with that many digits, the one
     * closest to the exact value of {@code x}.
     *
     * <p>A decimal converts back to {@code x} when it lies between the
     * midpoints to the neighbouring doubles; a decimal exactly on a midpoint
     * converts to the neighbour with the even significand.</p>
     */
    private static BigDecimal shortestDecimal(double x) {
        BigDecimal exact = new BigDecimal(x);
        double below = Math.nextDown(x);
        double above = Math.nextUp(x);
        BigDecimal half = new BigDecimal("0.5");
        BigDecimal lowMid = exact.add(new BigDecimal(below)).multiply(half);
        BigDecimal highMid = Double.isInfinite(above)
                // Above the largest double the next value would be 2^1024.
                ? exact.add(exact.subtract(new BigDecimal(below)).multiply(half))
                : exact.add(new BigDecimal(above)).multiply(half);
        boolean even = (Double.doubleToRawLongBits(x) & 1L) == 0;

        for (int precision = 1; precision <= 17; precision++) {
            BigDecimal down = exact.round(new MathContext(precision, RoundingMode.DOWN));
            BigDecimal up = exact.round(new MathContext(precision, RoundingMode.UP));
            boolean downOk = roundTrips(down, lowMid, highMid, even);
            boolean upOk = roundTrips(up, lowMid, highMid, even);
            if (downOk && upOk) {
                int cmp = exact.subtract(down).compareTo(up.subtract(exact));
                if (cmp < 0) return down;
                if (cmp > 0) return up;
                // Equally close: the candidate whose last digit is even.
                return down.unscaledValue().testBit(0) ? up : down;
            }
            if (downOk) return down;
            if (upOk) return up;
        }
        // 17 significant digits always identify a double.
        throw new IllegalStateException("no round-trip decimal found for " + x);
    }

    private static boolean roundTrips(BigDecimal candidate, BigDecimal lowMid, BigDecimal highMid,
                                      boolean even) {
        int low = candidate.compareTo(lowMid);
        int high = candidate.compareTo(highMid);
        if (low > 0 && high < 0) return true;
        return even && (low == 0 || high == 0);
    }
}
