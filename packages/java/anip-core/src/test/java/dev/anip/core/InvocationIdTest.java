package dev.anip.core;

import org.junit.jupiter.api.Test;

import java.util.HashSet;
import java.util.Set;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.*;

class InvocationIdTest {

    private static final Pattern ID_PATTERN = Pattern.compile("^inv-[0-9a-f]{12}$");

    @Test
    void formatMatchesPattern() {
        String id = Constants.generateInvocationId();
        assertTrue(ID_PATTERN.matcher(id).matches(),
                "invocation ID '" + id + "' does not match pattern inv-[0-9a-f]{12}");
    }

    @Test
    void eachCallGeneratesUniqueId() {
        String id1 = Constants.generateInvocationId();
        String id2 = Constants.generateInvocationId();
        assertNotEquals(id1, id2, "two invocation IDs should be unique");
    }

    @Test
    void manyIdsAreUnique() {
        Set<String> ids = new HashSet<>();
        for (int i = 0; i < 1000; i++) {
            String id = Constants.generateInvocationId();
            assertTrue(ID_PATTERN.matcher(id).matches(),
                    "invocation ID '" + id + "' does not match pattern");
            assertTrue(ids.add(id), "duplicate invocation ID: " + id);
        }
    }
}
