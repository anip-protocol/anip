/**
 * Produce a deterministic JSON string from an object.
 *
 * Keys are sorted lexicographically and any keys listed in `exclude` are
 * omitted before serialisation.
 */
export function canonicalize(
  data: Record<string, unknown>,
  exclude?: Set<string>,
): string {
  const filtered = Object.fromEntries(
    Object.entries(data)
      .filter(([k]) => !exclude?.has(k))
      .sort(([a], [b]) => a.localeCompare(b)),
  );
  return JSON.stringify(filtered);
}
