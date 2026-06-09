package dev.anip.generated.gtm_operator_contract_20260512235040;

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
        assertEquals("gtm.pipeline_summary", capabilities.get(0).getDeclaration().getName());
    }
}
