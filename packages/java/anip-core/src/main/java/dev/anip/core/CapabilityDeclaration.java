package dev.anip.core;

import java.util.List;

/**
 * Full declaration of a service capability.
 */
public class CapabilityDeclaration {

    private final String name;
    private final String description;
    private final String contractVersion;
    private final List<CapabilityInput> inputs;
    private final CapabilityOutput output;
    private final SideEffect sideEffect;
    private final List<String> minimumScope;
    private final Cost cost;
    private final List<CapabilityRequirement> requires;
    private final List<String> responseModes;
    private final List<BindingRequirement> requiresBinding;
    private final List<ControlRequirement> controlRequirements;
    private final List<String> refreshVia;
    private final List<String> verifyVia;

    public CapabilityDeclaration(String name, String description, String contractVersion,
                                  List<CapabilityInput> inputs, CapabilityOutput output,
                                  SideEffect sideEffect, List<String> minimumScope,
                                  Cost cost, List<CapabilityRequirement> requires,
                                  List<String> responseModes) {
        this(name, description, contractVersion, inputs, output, sideEffect,
             minimumScope, cost, requires, responseModes, null, null, null, null);
    }

    public CapabilityDeclaration(String name, String description, String contractVersion,
                                  List<CapabilityInput> inputs, CapabilityOutput output,
                                  SideEffect sideEffect, List<String> minimumScope,
                                  Cost cost, List<CapabilityRequirement> requires,
                                  List<String> responseModes,
                                  List<BindingRequirement> requiresBinding,
                                  List<ControlRequirement> controlRequirements) {
        this(name, description, contractVersion, inputs, output, sideEffect,
             minimumScope, cost, requires, responseModes, requiresBinding, controlRequirements, null, null);
    }

    public CapabilityDeclaration(String name, String description, String contractVersion,
                                  List<CapabilityInput> inputs, CapabilityOutput output,
                                  SideEffect sideEffect, List<String> minimumScope,
                                  Cost cost, List<CapabilityRequirement> requires,
                                  List<String> responseModes,
                                  List<BindingRequirement> requiresBinding,
                                  List<ControlRequirement> controlRequirements,
                                  List<String> refreshVia,
                                  List<String> verifyVia) {
        this.name = name;
        this.description = description;
        this.contractVersion = contractVersion;
        this.inputs = inputs;
        this.output = output;
        this.sideEffect = sideEffect;
        this.minimumScope = minimumScope;
        this.cost = cost;
        this.requires = requires;
        this.responseModes = responseModes;
        this.requiresBinding = requiresBinding;
        this.controlRequirements = controlRequirements;
        this.refreshVia = refreshVia != null ? refreshVia : java.util.Collections.emptyList();
        this.verifyVia = verifyVia != null ? verifyVia : java.util.Collections.emptyList();
    }

    public String getName() {
        return name;
    }

    public String getDescription() {
        return description;
    }

    public String getContractVersion() {
        return contractVersion;
    }

    public List<CapabilityInput> getInputs() {
        return inputs;
    }

    public CapabilityOutput getOutput() {
        return output;
    }

    public SideEffect getSideEffect() {
        return sideEffect;
    }

    public List<String> getMinimumScope() {
        return minimumScope;
    }

    public Cost getCost() {
        return cost;
    }

    public List<CapabilityRequirement> getRequires() {
        return requires;
    }

    public List<String> getResponseModes() {
        return responseModes;
    }

    public List<BindingRequirement> getRequiresBinding() {
        return requiresBinding;
    }

    public List<ControlRequirement> getControlRequirements() {
        return controlRequirements;
    }

    public List<String> getRefreshVia() {
        return refreshVia;
    }

    public List<String> getVerifyVia() {
        return verifyVia;
    }
}
