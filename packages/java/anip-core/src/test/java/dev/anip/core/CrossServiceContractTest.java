package dev.anip.core;

import org.junit.jupiter.api.Test;

import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for CrossServiceContract, CrossServiceContractEntry, and RecoveryTarget (v0.21).
 */
class CrossServiceContractTest {

    // --- CrossServiceContractEntry ---

    @Test
    void crossServiceContractEntry_fieldsArePreserved() {
        ServiceCapabilityRef ref = new ServiceCapabilityRef("booking-service", "confirm_booking");
        CrossServiceContractEntry entry = new CrossServiceContractEntry(
                ref, true, "same_task", "downstream_acceptance");

        assertEquals("booking-service", entry.getTarget().getService());
        assertEquals("confirm_booking", entry.getTarget().getCapability());
        assertTrue(entry.isRequiredForTaskCompletion());
        assertEquals("same_task", entry.getContinuity());
        assertEquals("downstream_acceptance", entry.getCompletionMode());
    }

    @Test
    void crossServiceContractEntry_noArgConstructorAndSetters() {
        CrossServiceContractEntry entry = new CrossServiceContractEntry();
        ServiceCapabilityRef ref = new ServiceCapabilityRef("svc", "cap");
        entry.setTarget(ref);
        entry.setRequiredForTaskCompletion(false);
        entry.setContinuity("same_task");
        entry.setCompletionMode("followup_status");

        assertEquals("svc", entry.getTarget().getService());
        assertFalse(entry.isRequiredForTaskCompletion());
        assertEquals("followup_status", entry.getCompletionMode());
    }

    // --- CrossServiceContract ---

    @Test
    void crossServiceContract_fieldsArePreserved() {
        ServiceCapabilityRef ref = new ServiceCapabilityRef("booking-service", "confirm_booking");
        CrossServiceContractEntry entry = new CrossServiceContractEntry(
                ref, true, "same_task", "downstream_acceptance");

        CrossServiceContract contract = new CrossServiceContract(
                List.of(entry), Collections.emptyList(), Collections.emptyList());

        assertEquals(1, contract.getHandoff().size());
        assertEquals("booking-service", contract.getHandoff().get(0).getTarget().getService());
        assertTrue(contract.getFollowup().isEmpty());
        assertTrue(contract.getVerification().isEmpty());
    }

    @Test
    void crossServiceContract_defaultsToEmptyLists() {
        CrossServiceContract contract = new CrossServiceContract(null, null, null);
        assertNotNull(contract.getHandoff());
        assertTrue(contract.getHandoff().isEmpty());
        assertNotNull(contract.getFollowup());
        assertTrue(contract.getFollowup().isEmpty());
        assertNotNull(contract.getVerification());
        assertTrue(contract.getVerification().isEmpty());
    }

    @Test
    void crossServiceContract_noArgConstructorAndSetters() {
        CrossServiceContract contract = new CrossServiceContract();
        ServiceCapabilityRef ref = new ServiceCapabilityRef("notify-service", "send_notification");
        CrossServiceContractEntry entry = new CrossServiceContractEntry(
                ref, false, "same_task", "followup_status");
        contract.setFollowup(List.of(entry));

        assertEquals(1, contract.getFollowup().size());
        assertEquals("notify-service", contract.getFollowup().get(0).getTarget().getService());
    }

    // --- RecoveryTarget ---

    @Test
    void recoveryTarget_fieldsArePreserved() {
        ServiceCapabilityRef ref = new ServiceCapabilityRef("auth-service", "refresh_token");
        RecoveryTarget rt = new RecoveryTarget("refresh", ref, "same_task", true);

        assertEquals("refresh", rt.getKind());
        assertNotNull(rt.getTarget());
        assertEquals("auth-service", rt.getTarget().getService());
        assertEquals("refresh_token", rt.getTarget().getCapability());
        assertEquals("same_task", rt.getContinuity());
        assertTrue(rt.isRetryAfterTarget());
    }

    @Test
    void recoveryTarget_nullTarget() {
        RecoveryTarget rt = new RecoveryTarget("escalation", null, "same_task", false);
        assertEquals("escalation", rt.getKind());
        assertNull(rt.getTarget());
        assertFalse(rt.isRetryAfterTarget());
    }

    @Test
    void recoveryTarget_noArgConstructorAndSetters() {
        RecoveryTarget rt = new RecoveryTarget();
        rt.setKind("redelegation");
        rt.setContinuity("same_task");
        rt.setRetryAfterTarget(true);

        assertEquals("redelegation", rt.getKind());
        assertEquals("same_task", rt.getContinuity());
        assertTrue(rt.isRetryAfterTarget());
    }

    @Test
    void recoveryTarget_allKindsAccepted() {
        for (String kind : new String[]{"refresh", "redelegation", "revalidation", "escalation"}) {
            RecoveryTarget rt = new RecoveryTarget(kind, null, "same_task", false);
            assertEquals(kind, rt.getKind());
        }
    }

    // --- CapabilityDeclaration with cross_service_contract ---

    @Test
    void capabilityDeclaration_withCrossServiceContract() {
        ServiceCapabilityRef ref = new ServiceCapabilityRef("booking-service", "confirm_booking");
        CrossServiceContractEntry entry = new CrossServiceContractEntry(
                ref, true, "same_task", "downstream_acceptance");
        CrossServiceContract contract = new CrossServiceContract(
                List.of(entry), Collections.emptyList(), Collections.emptyList());

        CapabilityDeclaration decl = new CapabilityDeclaration(
                "search_flights", "Search for flights", "1.0",
                Collections.emptyList(),
                new CapabilityOutput("object", List.of("flights")),
                new SideEffect("read", "not_applicable"),
                List.of("travel.search"),
                null,
                Collections.emptyList(),
                List.of("unary"),
                null, null, null, null, null,
                contract);

        assertNotNull(decl.getCrossServiceContract());
        assertEquals(1, decl.getCrossServiceContract().getHandoff().size());
        assertEquals("booking-service",
                decl.getCrossServiceContract().getHandoff().get(0).getTarget().getService());
    }

    @Test
    void capabilityDeclaration_crossServiceContractNullByDefault() {
        CapabilityDeclaration decl = new CapabilityDeclaration(
                "test", "Test", "1.0",
                Collections.emptyList(),
                new CapabilityOutput("object", Collections.emptyList()),
                new SideEffect("read", "not_applicable"),
                List.of("test"),
                null,
                Collections.emptyList(),
                List.of("unary"));

        assertNull(decl.getCrossServiceContract());
    }

    // --- Resolution with recovery_target ---

    @Test
    void resolution_withRecoveryTarget() {
        ServiceCapabilityRef ref = new ServiceCapabilityRef("auth-service", "refresh_token");
        RecoveryTarget rt = new RecoveryTarget("refresh", ref, "same_task", true);
        Resolution resolution = new Resolution(
                "obtain_binding",
                Constants.recoveryClassForAction("obtain_binding"),
                null, null, null,
                rt);

        assertEquals("obtain_binding", resolution.getAction());
        assertNotNull(resolution.getRecoveryTarget());
        assertEquals("refresh", resolution.getRecoveryTarget().getKind());
        assertNotNull(resolution.getRecoveryTarget().getTarget());
        assertEquals("auth-service", resolution.getRecoveryTarget().getTarget().getService());
        assertTrue(resolution.getRecoveryTarget().isRetryAfterTarget());
    }

    @Test
    void resolution_recoveryTargetNullByDefault() {
        Resolution resolution = new Resolution(
                "request_broader_scope",
                Constants.recoveryClassForAction("request_broader_scope"),
                null, null, null);

        assertNull(resolution.getRecoveryTarget());
    }
}
