package dev.anip.generated.notion_governed_fronting_showcase;

import dev.anip.service.CapabilityDef;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertEquals;

class GeneratedCapabilitiesTest {

    @Test
    void createsCapabilityDefinitions() {
        List<CapabilityDef> capabilities = GeneratedCapabilities.createAll(BackendAdapter.defaultAdapter());
        assertFalse(capabilities.isEmpty());
        assertEquals("notion.workspace.search_context", capabilities.get(0).getDeclaration().getName());
    }
}
