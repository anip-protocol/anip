export interface InputSpec {
  name?: string;
  required?: boolean;
  default?: unknown;
  allowed_values?: unknown[];
  semantic_type?: string;
  description?: string;
  resolution?: {
    on_missing?: string;
  };
}

export interface CapabilityMetadata {
  capability_id?: string;
  id?: string;
  description?: string;
  capability_framing?: string;
  summary?: string;
  output_intent?: string;
  business_effects?: {
    produces?: unknown[];
    does_not_produce?: unknown[];
  };
  input_specs?: InputSpec[];
  app_profile?: {
    capability_framing?: string;
    input_meanings?: Record<string, Record<string, unknown>>;
    app_boundaries?: {
      unsupported_effects?: unknown[];
      unsupported_terms?: Record<string, unknown[]>;
    };
    intent?: {
      category?: string;
      summary?: string;
    };
  };
  app_boundaries?: {
    unsupported_effects?: unknown[];
    unsupported_terms?: Record<string, unknown[]>;
  };
}

type CapabilityCatalog = Record<string, CapabilityMetadata | unknown>;

const EFFECT_TERMS: Record<string, Set<string>> = {
  "approval.execute": new Set(["approve", "apply", "commit", "execute", "perform"]),
  external_dispatch: new Set(["deliver", "dispatch", "publish", "send", "ship"]),
  raw_data_export: new Set(["csv", "download", "dump", "export", "raw", "spreadsheet"]),
  "system.mutation": new Set(["apply", "commit", "delete", "mutate", "update"]),
};

const NEGATION_TERMS = new Set(["avoid", "exclude", "no", "not", "without"]);
const CAPABILITY_SCORING_STOP_TOKENS = new Set([
  "after",
  "and",
  "before",
  "for",
  "in",
  "of",
  "that",
  "the",
  "these",
  "this",
  "those",
  "to",
  "with",
]);
const WEAK_INPUT_TOKENS = new Set([
  "id",
  "ids",
  "input",
  "name",
  "names",
  "ref",
  "reference",
  "value",
  "values",
]);

export function semanticTextKey(value: unknown): string {
  return String(value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
}

export function textTokens(value: unknown): Set<string> {
  return new Set(
    String(value ?? "")
      .toLowerCase()
      .replace(/_/g, " ")
      .match(/[a-z0-9]+/g)
      ?.filter((token) => token.length > 1) ?? [],
  );
}

function orderedTextTokens(value: unknown): string[] {
  return (
    String(value ?? "")
      .toLowerCase()
      .replace(/_/g, " ")
      .match(/[a-z0-9]+/g)
      ?.filter((token) => token.length > 1) ?? []
  );
}

function tokenVariants(tokens: Set<string>): Set<string> {
  const variants = new Set(tokens);
  for (const token of tokens) {
    if (token.length <= 3) {
      continue;
    }
    if (token.endsWith("ies") && token.length > 4) {
      variants.add(`${token.slice(0, -3)}y`);
    }
    if (token.endsWith("ing") && token.length > 5) {
      variants.add(token.slice(0, -3));
    }
    if (token.endsWith("ed") && token.length > 4) {
      variants.add(token.slice(0, -2));
    }
    if (token.endsWith("es") && token.length > 4) {
      variants.add(token.slice(0, -2));
    }
    if (token.endsWith("s") && token.length > 4) {
      variants.add(token.slice(0, -1));
    } else {
      variants.add(`${token}s`);
    }
  }
  return variants;
}

function metadataRecord(value: unknown): CapabilityMetadata {
  return isRecord(value) ? (value as CapabilityMetadata) : {};
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item ?? "")).filter((item) => item.length > 0)
    : [];
}

function capabilityProduces(metadata: CapabilityMetadata): Set<string> {
  return new Set(stringList(metadata.business_effects?.produces));
}

function capabilityDoesNotProduce(metadata: CapabilityMetadata): Set<string> {
  const boundaries = appBoundaries(metadata);
  const unsupportedEffects = stringList(boundaries.unsupported_effects);
  return new Set(
    unsupportedEffects.length > 0
      ? unsupportedEffects
      : stringList(metadata.business_effects?.does_not_produce),
  );
}

function appBoundaries(
  metadata: CapabilityMetadata,
): NonNullable<CapabilityMetadata["app_boundaries"]> {
  return metadata.app_profile?.app_boundaries ?? metadata.app_boundaries ?? {};
}

function inputMeaningsFor(
  metadata: CapabilityMetadata,
  inputName: string,
): Record<string, unknown> {
  return metadata.app_profile?.input_meanings?.[inputName] ?? {};
}

function inputCandidateValues(metadata: CapabilityMetadata, spec: InputSpec): string[] {
  const inputName = String(spec.name ?? "");
  const meanings = inputMeaningsFor(metadata, inputName);
  return [
    ...stringList(spec.allowed_values),
    ...Object.keys(meanings),
    ...Object.values(meanings).map((value) => String(value ?? "")),
  ].filter((value) => value.trim().length > 0);
}

function conversationContainsValue(conversation: string, value: string): boolean {
  const conversationKey = semanticTextKey(conversation);
  const valueKey = semanticTextKey(value);
  if (!valueKey) {
    return false;
  }
  return (
    conversationKey.includes(valueKey) ||
    [...textTokens(value)].every((token) => textTokens(conversation).has(token))
  );
}

function inputHasDefault(spec: InputSpec): boolean {
  const value = spec.default;
  return value !== undefined && value !== null && value !== "" && !(Array.isArray(value) && value.length === 0);
}

export function missingRequiredInputNames(
  conversation: string,
  rawMetadata: CapabilityMetadata | unknown,
): string[] {
  const metadata = metadataRecord(rawMetadata);
  const missing: string[] = [];
  for (const spec of metadata.input_specs ?? []) {
    if (!isRecord(spec) || spec.required !== true) {
      continue;
    }
    const inputSpec = spec as InputSpec;
    const name = String(inputSpec.name ?? "");
    if (!name) {
      continue;
    }
    if (inputHasDefault(inputSpec) && inputSpec.resolution?.on_missing === "use_default") {
      continue;
    }
    const values = inputCandidateValues(metadata, inputSpec);
    const grounded = values.some((value) => conversationContainsValue(conversation, value));
    if (!grounded) {
      missing.push(name);
    }
  }
  return missing;
}

function termIsNegated(tokens: string[], term: string): boolean {
  for (const [index, token] of tokens.entries()) {
    if (token !== term) {
      continue;
    }
    const window = tokens.slice(Math.max(0, index - 6), index);
    if (window.some((item) => NEGATION_TERMS.has(item))) {
      return true;
    }
    if (window.length >= 2 && window.at(-2) === "do" && window.at(-1) === "not") {
      return true;
    }
  }
  return false;
}

export function requestedUnsupportedEffects(
  conversation: string,
  rawMetadata: CapabilityMetadata | unknown,
): string[] {
  const metadata = metadataRecord(rawMetadata);
  const tokens = textTokens(conversation);
  const orderedTokens = orderedTextTokens(conversation);
  const blocked = capabilityDoesNotProduce(metadata);
  const produced = capabilityProduces(metadata);
  const requested = new Set<string>();
  const boundaries = appBoundaries(metadata);
  const lowered = conversation.toLowerCase();

  if (boundaries.unsupported_terms && isRecord(boundaries.unsupported_terms)) {
    for (const [effect, terms] of Object.entries(boundaries.unsupported_terms)) {
      if (stringList(terms).some((term) => term && lowered.includes(term.toLowerCase()))) {
        requested.add(effect);
      }
    }
  }

  for (const [effect, terms] of Object.entries(EFFECT_TERMS)) {
    const matchedTerms = [...tokens].filter((token) => terms.has(token));
    if (matchedTerms.length === 0) {
      continue;
    }
    if (matchedTerms.every((term) => termIsNegated(orderedTokens, term))) {
      continue;
    }
    if (
      blocked.has(effect) ||
      (effect === "raw_data_export" && !produced.has("raw_data_export")) ||
      (effect === "external_dispatch" && produced.has("content.draft"))
    ) {
      requested.add(effect);
    }
  }

  return [...requested].sort();
}

export const detectUnsupportedEffects = requestedUnsupportedEffects;

function inputReferenceTokens(metadata: CapabilityMetadata, inputName: string): Set<string> {
  const spec =
    metadata.input_specs?.find((item) => isRecord(item) && String(item.name ?? "") === inputName) ??
    {};
  const tokens = textTokens(
    [
      inputName,
      isRecord(spec) ? spec.semantic_type : "",
      isRecord(spec) ? spec.description : "",
    ].join(" "),
  );
  return new Set([...tokens].filter((token) => !WEAK_INPUT_TOKENS.has(token)));
}

function missingRequiredInputsAreReferenced(
  conversation: string,
  metadata: CapabilityMetadata,
  missingInputs: string[],
): boolean {
  if (missingInputs.length === 0) {
    return false;
  }
  const conversationTokens = textTokens(conversation);
  if (conversationTokens.size === 0) {
    return false;
  }
  return missingInputs.every((inputName) => {
    const tokens = inputReferenceTokens(metadata, inputName);
    return tokens.size > 0 && [...tokens].some((token) => conversationTokens.has(token));
  });
}

function sameEffectClass(first: CapabilityMetadata, second: CapabilityMetadata): boolean {
  const firstProduces = capabilityProduces(first);
  const secondProduces = capabilityProduces(second);
  return [...firstProduces].some((effect) => secondProduces.has(effect));
}

function scoreTokens(value: unknown): Set<string> {
  return tokenVariants(
    new Set(
      [...textTokens(value)].filter(
        (token) =>
          !CAPABILITY_SCORING_STOP_TOKENS.has(token) &&
          !/^(?:19|20)\d{2}$/.test(token),
      ),
    ),
  );
}

export function capabilityMatchScore(
  conversation: string,
  capabilityId: string,
  rawMetadata: CapabilityMetadata | unknown,
): number {
  const metadata = metadataRecord(rawMetadata);
  const inputFragments: string[] = [];
  for (const spec of metadata.input_specs ?? []) {
    if (!isRecord(spec)) {
      continue;
    }
    inputFragments.push(String(spec.name ?? ""));
    inputFragments.push(String(spec.semantic_type ?? ""));
    inputFragments.push(String(spec.description ?? ""));
    inputFragments.push(...stringList(spec.allowed_values));
  }

  const appProfile = metadata.app_profile;
  const haystack = [
    capabilityId,
    metadata.capability_id,
    metadata.id,
    metadata.description,
    metadata.capability_framing,
    metadata.summary,
    metadata.output_intent,
    appProfile?.capability_framing,
    appProfile?.intent?.category,
    appProfile?.intent?.summary,
    JSON.stringify(appProfile?.input_meanings ?? {}),
    JSON.stringify(appProfile?.app_boundaries ?? {}),
    inputFragments.join(" "),
  ].join(" ");

  const sourceTokens = scoreTokens(conversation);
  const targetTokens = scoreTokens(haystack);
  if (sourceTokens.size === 0 || targetTokens.size === 0) {
    return 0;
  }

  const overlap = [...sourceTokens].filter((token) => targetTokens.has(token));
  const recall = overlap.length / sourceTokens.size;
  const precision = overlap.length / targetTokens.size;
  const idTokens = scoreTokens(capabilityId);
  const idPrecision =
    idTokens.size === 0
      ? 0
      : [...sourceTokens].filter((token) => idTokens.has(token)).length / idTokens.size;

  return recall * 0.65 + precision * 0.25 + idPrecision * 0.1;
}

export function selectConsumableCapability(
  conversation: string,
  selectedCapability: string,
  rawMetadata: CapabilityCatalog,
): string {
  const selectedMetadata = metadataRecord(rawMetadata[selectedCapability]);
  if (Object.keys(selectedMetadata).length === 0) {
    return selectedCapability;
  }

  const selectedMissing = missingRequiredInputNames(conversation, selectedMetadata);
  const selectedScore = capabilityMatchScore(conversation, selectedCapability, selectedMetadata);
  let bestCapability = selectedCapability;
  let bestScore = selectedScore;

  for (const [capabilityId, value] of Object.entries(rawMetadata)) {
    if (capabilityId === selectedCapability) {
      continue;
    }
    const candidate = metadataRecord(value);
    if (!sameEffectClass(selectedMetadata, candidate)) {
      continue;
    }
    const missing = missingRequiredInputNames(conversation, candidate);
    if (
      selectedMissing.length > 0 &&
      missing.length > 0 &&
      !missingRequiredInputsAreReferenced(conversation, candidate, missing)
    ) {
      continue;
    }
    const score = capabilityMatchScore(conversation, capabilityId, candidate);
    if (score > bestScore) {
      bestCapability = capabilityId;
      bestScore = score;
    }
  }

  return bestCapability !== selectedCapability && bestScore >= Math.max(0.12, selectedScore + 0.08)
    ? bestCapability
    : selectedCapability;
}
