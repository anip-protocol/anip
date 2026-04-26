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
    private final List<CapabilityComposition> composesWith;
    private final List<String> responseModes;
    private final List<BindingRequirement> requiresBinding;
    private final List<ControlRequirement> controlRequirements;
    private final List<String> refreshVia;
    private final List<String> verifyVia;
    private final CrossServiceHints crossService;
    private final CrossServiceContract crossServiceContract;
    // v0.23 — composition + approval grant policy. Mutable for builder/setter style;
    // values default to null/atomic so existing callers do not break.
    private String kind = "atomic";
    private Composition composition;
    private GrantPolicy grantPolicy;

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
        this(name, description, contractVersion, inputs, output, sideEffect,
             minimumScope, cost, requires, responseModes, requiresBinding, controlRequirements,
             refreshVia, verifyVia, null);
    }

    public CapabilityDeclaration(String name, String description, String contractVersion,
                                  List<CapabilityInput> inputs, CapabilityOutput output,
                                  SideEffect sideEffect, List<String> minimumScope,
                                  Cost cost, List<CapabilityRequirement> requires,
                                  List<String> responseModes,
                                  List<BindingRequirement> requiresBinding,
                                  List<ControlRequirement> controlRequirements,
                                  List<String> refreshVia,
                                  List<String> verifyVia,
                                  CrossServiceHints crossService) {
        this(name, description, contractVersion, inputs, output, sideEffect,
             minimumScope, cost, requires, responseModes, requiresBinding, controlRequirements,
             refreshVia, verifyVia, crossService, null);
    }

    public CapabilityDeclaration(String name, String description, String contractVersion,
                                  List<CapabilityInput> inputs, CapabilityOutput output,
                                  SideEffect sideEffect, List<String> minimumScope,
                                  Cost cost, List<CapabilityRequirement> requires,
                                  List<String> responseModes,
                                  List<BindingRequirement> requiresBinding,
                                  List<ControlRequirement> controlRequirements,
                                  List<String> refreshVia,
                                  List<String> verifyVia,
                                  CrossServiceHints crossService,
                                  CrossServiceContract crossServiceContract) {
        this(name, description, contractVersion, inputs, output, sideEffect,
             minimumScope, cost, requires, responseModes, requiresBinding, controlRequirements,
             refreshVia, verifyVia, crossService, crossServiceContract, null);
    }

    public CapabilityDeclaration(String name, String description, String contractVersion,
                                  List<CapabilityInput> inputs, CapabilityOutput output,
                                  SideEffect sideEffect, List<String> minimumScope,
                                  Cost cost, List<CapabilityRequirement> requires,
                                  List<String> responseModes,
                                  List<BindingRequirement> requiresBinding,
                                  List<ControlRequirement> controlRequirements,
                                  List<String> refreshVia,
                                  List<String> verifyVia,
                                  CrossServiceHints crossService,
                                  CrossServiceContract crossServiceContract,
                                  List<CapabilityComposition> composesWith) {
        this.name = name;
        this.description = description;
        this.contractVersion = contractVersion;
        this.inputs = inputs;
        this.output = output;
        this.sideEffect = sideEffect;
        this.minimumScope = minimumScope;
        this.cost = cost;
        this.requires = requires;
        this.composesWith = composesWith;
        this.responseModes = responseModes;
        this.requiresBinding = requiresBinding;
        this.controlRequirements = controlRequirements;
        this.refreshVia = refreshVia != null ? refreshVia : java.util.Collections.emptyList();
        this.verifyVia = verifyVia != null ? verifyVia : java.util.Collections.emptyList();
        this.crossService = crossService;
        this.crossServiceContract = crossServiceContract;
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

    public List<CapabilityComposition> getComposesWith() {
        return composesWith;
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

    public CrossServiceHints getCrossService() {
        return crossService;
    }

    public CrossServiceContract getCrossServiceContract() {
        return crossServiceContract;
    }

    // v0.23 accessors
    public String getKind() {
        return kind;
    }

    public CapabilityDeclaration setKind(String kind) {
        this.kind = kind;
        return this;
    }

    public Composition getComposition() {
        return composition;
    }

    public CapabilityDeclaration setComposition(Composition composition) {
        this.composition = composition;
        return this;
    }

    public GrantPolicy getGrantPolicy() {
        return grantPolicy;
    }

    public CapabilityDeclaration setGrantPolicy(GrantPolicy grantPolicy) {
        this.grantPolicy = grantPolicy;
        return this;
    }
}
