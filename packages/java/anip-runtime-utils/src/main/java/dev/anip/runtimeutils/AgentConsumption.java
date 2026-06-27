package dev.anip.runtimeutils;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class AgentConsumption {
    private static final Pattern TOKEN_PATTERN = Pattern.compile("[a-z0-9]+");
    private static final Pattern SEMANTIC_TEXT_PATTERN = Pattern.compile("[^a-z0-9]+");

    private static final Map<String, Set<String>> EFFECT_TERMS = Map.of(
            "approval.execute", Set.of("approve", "apply", "commit", "execute", "perform"),
            "external_dispatch", Set.of("deliver", "dispatch", "publish", "send", "ship"),
            "raw_data_export", Set.of("csv", "download", "dump", "export", "raw", "spreadsheet"),
            "system.mutation", Set.of("apply", "commit", "delete", "mutate", "update"));
    private static final Set<String> NEGATION_TERMS = Set.of("avoid", "exclude", "no", "not", "without");
    private static final Set<String> CAPABILITY_SCORING_STOP_TOKENS = Set.of(
            "after", "and", "before", "for", "in", "of", "that", "the", "these", "this", "those", "to", "with");
    private static final Set<String> WEAK_INPUT_TOKENS = Set.of(
            "id", "ids", "input", "name", "names", "ref", "reference", "value", "values");

    private AgentConsumption() {
    }

    public static String semanticTextKey(Object value) {
        return SEMANTIC_TEXT_PATTERN.matcher(stringValue(value).toLowerCase(Locale.ROOT)).replaceAll("");
    }

    public static Set<String> textTokens(Object value) {
        return new LinkedHashSet<>(orderedTextTokens(value));
    }

    public static List<String> missingRequiredInputNames(String conversation, Map<String, Object> metadata) {
        Map<String, Object> safeMetadata = mapValue(metadata);
        List<String> missing = new ArrayList<>();
        for (Object rawSpec : listValue(safeMetadata.get("input_specs"))) {
            Map<String, Object> spec = mapValue(rawSpec);
            if (!Boolean.TRUE.equals(spec.get("required"))) {
                continue;
            }
            String name = stringValue(spec.get("name"));
            if (name.isEmpty()) {
                continue;
            }
            if (inputHasDefault(spec) && "use_default".equals(stringValue(mapValue(spec.get("resolution")).get("on_missing")))) {
                continue;
            }
            if (!inputGrounded(conversation, inputCandidateValues(safeMetadata, spec))) {
                missing.add(name);
            }
        }
        return missing;
    }

    public static List<String> requestedUnsupportedEffects(String conversation, Map<String, Object> metadata) {
        Map<String, Object> safeMetadata = mapValue(metadata);
        Set<String> tokens = textTokens(conversation);
        List<String> orderedTokens = orderedTextTokens(conversation);
        Set<String> blocked = capabilityDoesNotProduce(safeMetadata);
        Set<String> produced = capabilityProduces(safeMetadata);
        Map<String, Object> boundaries = appBoundaries(safeMetadata);
        String lowered = stringValue(conversation).toLowerCase(Locale.ROOT);
        Set<String> requested = new HashSet<>();

        for (Map.Entry<String, Object> entry : mapValue(boundaries.get("unsupported_terms")).entrySet()) {
            for (String term : stringList(entry.getValue())) {
                if (!term.isEmpty() && lowered.contains(term.toLowerCase(Locale.ROOT))) {
                    requested.add(entry.getKey());
                }
            }
        }

        for (Map.Entry<String, Set<String>> entry : EFFECT_TERMS.entrySet()) {
            List<String> matchedTerms = new ArrayList<>();
            for (String term : entry.getValue()) {
                if (tokens.contains(term)) {
                    matchedTerms.add(term);
                }
            }
            if (matchedTerms.isEmpty()) {
                continue;
            }
            boolean allNegated = true;
            for (String term : matchedTerms) {
                if (!termIsNegated(orderedTokens, term)) {
                    allNegated = false;
                    break;
                }
            }
            String effect = entry.getKey();
            if (!allNegated && (blocked.contains(effect)
                    || ("raw_data_export".equals(effect) && !produced.contains("raw_data_export"))
                    || ("external_dispatch".equals(effect) && produced.contains("content.draft")))) {
                requested.add(effect);
            }
        }

        return sorted(requested);
    }

    public static List<String> detectUnsupportedEffects(String conversation, Map<String, Object> metadata) {
        return requestedUnsupportedEffects(conversation, metadata);
    }

    public static double capabilityMatchScore(String conversation, String capabilityId, Map<String, Object> metadata) {
        Map<String, Object> safeMetadata = mapValue(metadata);
        List<String> inputFragments = new ArrayList<>();
        for (Object rawSpec : listValue(safeMetadata.get("input_specs"))) {
            Map<String, Object> spec = mapValue(rawSpec);
            inputFragments.add(stringValue(spec.get("name")));
            inputFragments.add(stringValue(spec.get("semantic_type")));
            inputFragments.add(stringValue(spec.get("description")));
            inputFragments.addAll(stringList(spec.get("allowed_values")));
        }

        Map<String, Object> appProfile = mapValue(safeMetadata.get("app_profile"));
        Map<String, Object> intent = mapValue(appProfile.get("intent"));
        String haystack = String.join(" ", Arrays.asList(
                stringValue(capabilityId),
                stringValue(safeMetadata.get("capability_id")),
                stringValue(safeMetadata.get("id")),
                stringValue(safeMetadata.get("description")),
                stringValue(safeMetadata.get("capability_framing")),
                stringValue(safeMetadata.get("summary")),
                stringValue(safeMetadata.get("output_intent")),
                stringValue(appProfile.get("capability_framing")),
                stringValue(intent.get("category")),
                stringValue(intent.get("summary")),
                stringValue(appProfile.get("input_meanings")),
                stringValue(appProfile.get("app_boundaries")),
                String.join(" ", inputFragments)));

        Set<String> sourceTokens = scoreTokens(conversation);
        Set<String> targetTokens = scoreTokens(haystack);
        if (sourceTokens.isEmpty() || targetTokens.isEmpty()) {
            return 0.0;
        }

        int overlap = overlap(sourceTokens, targetTokens);
        double recall = (double) overlap / (double) sourceTokens.size();
        double precision = (double) overlap / (double) targetTokens.size();

        Set<String> idTokens = scoreTokens(capabilityId);
        double idPrecision = idTokens.isEmpty() ? 0.0 : (double) overlap(sourceTokens, idTokens) / (double) idTokens.size();
        return recall * 0.65 + precision * 0.25 + idPrecision * 0.1;
    }

    public static String selectConsumableCapability(
            String conversation,
            String selectedCapability,
            Map<String, Map<String, Object>> metadata) {
        if (metadata == null || !metadata.containsKey(selectedCapability)) {
            return selectedCapability;
        }

        Map<String, Object> selectedMetadata = mapValue(metadata.get(selectedCapability));
        List<String> selectedMissing = missingRequiredInputNames(conversation, selectedMetadata);
        double selectedScore = capabilityMatchScore(conversation, selectedCapability, selectedMetadata);
        String bestCapability = selectedCapability;
        double bestScore = selectedScore;

        for (Map.Entry<String, Map<String, Object>> entry : metadata.entrySet()) {
            String capabilityId = entry.getKey();
            Map<String, Object> candidate = mapValue(entry.getValue());
            if (capabilityId.equals(selectedCapability) || !sameEffectClass(selectedMetadata, candidate)) {
                continue;
            }
            List<String> missing = missingRequiredInputNames(conversation, candidate);
            if (!selectedMissing.isEmpty() && !missing.isEmpty() && !missingRequiredInputsAreReferenced(conversation, candidate, missing)) {
                continue;
            }
            double score = capabilityMatchScore(conversation, capabilityId, candidate);
            if (score > bestScore) {
                bestCapability = capabilityId;
                bestScore = score;
            }
        }

        if (!bestCapability.equals(selectedCapability) && bestScore >= Math.max(0.12, selectedScore + 0.08)) {
            return bestCapability;
        }
        return selectedCapability;
    }

    private static List<String> orderedTextTokens(Object value) {
        String normalized = stringValue(value).toLowerCase(Locale.ROOT).replace('_', ' ');
        Matcher matcher = TOKEN_PATTERN.matcher(normalized);
        List<String> tokens = new ArrayList<>();
        while (matcher.find()) {
            String token = matcher.group();
            if (token.length() > 1) {
                tokens.add(token);
            }
        }
        return tokens;
    }

    private static Set<String> tokenVariants(Set<String> tokens) {
        Set<String> variants = new LinkedHashSet<>(tokens);
        for (String token : tokens) {
            if (token.length() <= 3) {
                continue;
            }
            if (token.endsWith("ies") && token.length() > 4) {
                variants.add(token.substring(0, token.length() - 3) + "y");
            } else if (token.endsWith("ing") && token.length() > 5) {
                variants.add(token.substring(0, token.length() - 3));
            } else if (token.endsWith("ed") && token.length() > 4) {
                variants.add(token.substring(0, token.length() - 2));
            } else if (token.endsWith("es") && token.length() > 4) {
                variants.add(token.substring(0, token.length() - 2));
            } else if (token.endsWith("s") && token.length() > 4) {
                variants.add(token.substring(0, token.length() - 1));
            } else {
                variants.add(token + "s");
            }
        }
        return variants;
    }

    private static Set<String> scoreTokens(Object value) {
        Set<String> filtered = new LinkedHashSet<>();
        for (String token : textTokens(value)) {
            if (!CAPABILITY_SCORING_STOP_TOKENS.contains(token) && !isYearToken(token)) {
                filtered.add(token);
            }
        }
        return tokenVariants(filtered);
    }

    private static Map<String, Object> mapValue(Object value) {
        if (!(value instanceof Map<?, ?> rawMap)) {
            return Collections.emptyMap();
        }
        Map<String, Object> out = new HashMap<>();
        for (Map.Entry<?, ?> entry : rawMap.entrySet()) {
            out.put(stringValue(entry.getKey()), entry.getValue());
        }
        return out;
    }

    private static List<Object> listValue(Object value) {
        if (!(value instanceof Collection<?> collection)) {
            return Collections.emptyList();
        }
        return new ArrayList<>(collection);
    }

    private static List<String> stringList(Object value) {
        List<String> out = new ArrayList<>();
        for (Object item : listValue(value)) {
            String text = stringValue(item);
            if (!text.isEmpty()) {
                out.add(text);
            }
        }
        return out;
    }

    private static String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private static boolean inputHasDefault(Map<String, Object> spec) {
        if (!spec.containsKey("default")) {
            return false;
        }
        Object value = spec.get("default");
        if (value == null) {
            return false;
        }
        if (value instanceof String text) {
            return !text.isEmpty();
        }
        if (value instanceof Collection<?> collection) {
            return !collection.isEmpty();
        }
        return true;
    }

    private static List<String> inputCandidateValues(Map<String, Object> metadata, Map<String, Object> spec) {
        String inputName = stringValue(spec.get("name"));
        Map<String, Object> meanings = mapValue(mapValue(metadata.get("app_profile")).get("input_meanings"));
        Map<String, Object> inputMeanings = mapValue(meanings.get(inputName));
        List<String> values = new ArrayList<>(stringList(spec.get("allowed_values")));
        for (Map.Entry<String, Object> entry : inputMeanings.entrySet()) {
            if (!entry.getKey().isEmpty()) {
                values.add(entry.getKey());
            }
            String text = stringValue(entry.getValue());
            if (!text.isEmpty()) {
                values.add(text);
            }
        }
        return values;
    }

    private static boolean inputGrounded(String conversation, List<String> values) {
        String conversationKey = semanticTextKey(conversation);
        Set<String> conversationTokens = textTokens(conversation);
        for (String value : values) {
            String valueKey = semanticTextKey(value);
            if (valueKey.isEmpty()) {
                continue;
            }
            if (conversationKey.contains(valueKey)) {
                return true;
            }
            Set<String> valueTokens = textTokens(value);
            if (!valueTokens.isEmpty() && conversationTokens.containsAll(valueTokens)) {
                return true;
            }
        }
        return false;
    }

    private static Set<String> capabilityProduces(Map<String, Object> metadata) {
        return new HashSet<>(stringList(mapValue(metadata.get("business_effects")).get("produces")));
    }

    private static Set<String> capabilityDoesNotProduce(Map<String, Object> metadata) {
        Map<String, Object> boundaries = appBoundaries(metadata);
        List<String> unsupported = stringList(boundaries.get("unsupported_effects"));
        if (!unsupported.isEmpty()) {
            return new HashSet<>(unsupported);
        }
        return new HashSet<>(stringList(mapValue(metadata.get("business_effects")).get("does_not_produce")));
    }

    private static Map<String, Object> appBoundaries(Map<String, Object> metadata) {
        Map<String, Object> boundaries = mapValue(mapValue(metadata.get("app_profile")).get("app_boundaries"));
        return boundaries.isEmpty() ? mapValue(metadata.get("app_boundaries")) : boundaries;
    }

    private static boolean termIsNegated(List<String> tokens, String term) {
        for (int index = 0; index < tokens.size(); index++) {
            if (!term.equals(tokens.get(index))) {
                continue;
            }
            int start = Math.max(0, index - 6);
            List<String> window = tokens.subList(start, index);
            for (String item : window) {
                if (NEGATION_TERMS.contains(item)) {
                    return true;
                }
            }
            if (window.size() >= 2
                    && "do".equals(window.get(window.size() - 2))
                    && "not".equals(window.get(window.size() - 1))) {
                return true;
            }
        }
        return false;
    }

    private static Set<String> inputReferenceTokens(Map<String, Object> metadata, String inputName) {
        Map<String, Object> spec = Collections.emptyMap();
        for (Object rawSpec : listValue(metadata.get("input_specs"))) {
            Map<String, Object> candidate = mapValue(rawSpec);
            if (inputName.equals(stringValue(candidate.get("name")))) {
                spec = candidate;
                break;
            }
        }
        Set<String> tokens = textTokens(String.join(" ", Arrays.asList(
                inputName,
                stringValue(spec.get("semantic_type")),
                stringValue(spec.get("description")))));
        tokens.removeAll(WEAK_INPUT_TOKENS);
        return tokens;
    }

    private static boolean missingRequiredInputsAreReferenced(
            String conversation,
            Map<String, Object> metadata,
            List<String> missingInputs) {
        if (missingInputs.isEmpty()) {
            return false;
        }
        Set<String> conversationTokens = textTokens(conversation);
        if (conversationTokens.isEmpty()) {
            return false;
        }
        for (String inputName : missingInputs) {
            Set<String> tokens = inputReferenceTokens(metadata, inputName);
            if (tokens.isEmpty() || Collections.disjoint(tokens, conversationTokens)) {
                return false;
            }
        }
        return true;
    }

    private static boolean sameEffectClass(Map<String, Object> first, Map<String, Object> second) {
        Set<String> firstProduces = capabilityProduces(first);
        Set<String> secondProduces = capabilityProduces(second);
        return !Collections.disjoint(firstProduces, secondProduces);
    }

    private static int overlap(Set<String> first, Set<String> second) {
        int count = 0;
        for (String token : first) {
            if (second.contains(token)) {
                count++;
            }
        }
        return count;
    }

    private static List<String> sorted(Set<String> values) {
        List<String> out = new ArrayList<>(values);
        Collections.sort(out);
        return out;
    }

    private static boolean isYearToken(String token) {
        if (token.length() != 4 || !(token.startsWith("19") || token.startsWith("20"))) {
            return false;
        }
        for (int index = 0; index < token.length(); index++) {
            if (!Character.isDigit(token.charAt(index))) {
                return false;
            }
        }
        return true;
    }
}
