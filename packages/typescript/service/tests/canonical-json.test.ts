/**
 * Canonical JSON for approval digests is RFC 8785 (SPEC.md §4.7 "Canonical
 * JSON and Digests"). The vectors are shared by every runtime.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { canonicalJson, sha256Digest } from "../src/index.js";

interface Vector {
  name: string;
  input: string;
  canonical: string;
  canonical_utf8_hex: string;
  sha256: string;
}

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(
  readFileSync(resolve(__dirname, "../../../canonical-json-fixtures/rfc8785-vectors.json"), "utf8"),
) as { vectors: Vector[] };

describe("shared RFC 8785 vectors", () => {
  it("the fixture file has vectors", () => {
    expect(fixture.vectors.length).toBeGreaterThanOrEqual(65);
  });

  // JSON.parse is the parser behind every HTTP binding's invocation body
  // (express.json(), Hono's c.req.json(), Fastify's JSON content parser).
  for (const vector of fixture.vectors) {
    it(vector.name, () => {
      const value: unknown = JSON.parse(vector.input);
      const canonical = canonicalJson(value);
      expect(Buffer.from(canonical, "utf8").toString("hex")).toBe(vector.canonical_utf8_hex);
      expect(canonical).toBe(vector.canonical);
      expect(sha256Digest(value)).toBe(vector.sha256);
    });
  }
});

describe("canonicalJson on values that did not come from a JSON text", () => {
  it("writes -0 as 0", () => {
    expect(canonicalJson(-0)).toBe("0");
    expect(canonicalJson({ a: [-0] })).toBe('{"a":[0]}');
  });

  it("refuses NaN and the infinities", () => {
    for (const value of [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]) {
      expect(() => canonicalJson(value)).toThrow(/RFC 8785/);
      expect(() => canonicalJson({ a: [1, value] })).toThrow(/RFC 8785/);
      expect(() => sha256Digest({ a: value })).toThrow(/RFC 8785/);
    }
  });

  it("converts a bigint to an IEEE 754 double first", () => {
    expect(canonicalJson(5n)).toBe("5");
    expect(canonicalJson(9007199254740993n)).toBe("9007199254740992");
    expect(canonicalJson(10n ** 21n)).toBe("1e+21");
    expect(() => canonicalJson(10n ** 400n)).toThrow(/RFC 8785/);
  });

  it("leaves out an undefined member, as JSON does, and writes an undefined element as null", () => {
    expect(canonicalJson({ b: undefined, a: 1 })).toBe('{"a":1}');
    expect(sha256Digest({ b: undefined, a: 1 })).toBe(sha256Digest({ a: 1 }));
    expect(canonicalJson([1, undefined, 2])).toBe("[1,null,2]");
    expect(canonicalJson(undefined)).toBe("null");
  });

  it("round-trips through JSON: the digest of a value is the digest of its JSON text", () => {
    const value = { z: [1, 2.5, "é\u2028<", { k: null, j: undefined }], a: 1e21, "é": true };
    expect(canonicalJson(value)).toBe(canonicalJson(JSON.parse(JSON.stringify(value))));
  });

  it("refuses a lone surrogate (RFC 8785 §3.2.2.2)", () => {
    expect(() => canonicalJson("\ud800")).toThrow(/RFC 8785/);
    expect(() => canonicalJson({ "\udc00x": 1 })).toThrow(/RFC 8785/);
    expect(() => canonicalJson(["ok", "a\ud83d"])).toThrow(/RFC 8785/);
    expect(canonicalJson("😀")).toBe('"\u{1f600}"');
  });

  it("treats values JSON has no form for the way JSON.stringify does", () => {
    const date = new Date("2026-03-10T12:00:00.000Z");
    const value = { when: date, fn: () => 1, sym: Symbol("s"), list: [() => 1, Symbol("s")] };
    expect(canonicalJson(value)).toBe('{"list":[null,null],"when":"2026-03-10T12:00:00.000Z"}');
    expect(canonicalJson(value)).toBe(canonicalJson(JSON.parse(JSON.stringify(value))));
  });

  it("sorts member names by UTF-16 code units", () => {
    // U+1F600 is the surrogate pair D83D DE00, which sorts before U+FF5E.
    expect(canonicalJson({ "～": 1, "\u{1f600}": 2, a: 3 })).toBe('{"a":3,"\u{1f600}":2,"～":1}');
  });

  it("escapes only what RFC 8785 says", () => {
    expect(canonicalJson('"\\/\b\f\n\r\t\u0000\u001f\u007f\u2028\u2029<>&é')).toBe(
      '"\\"\\\\/\\b\\f\\n\\r\\t\\u0000\\u001f\u007f\u2028\u2029<>&é"',
    );
  });
});
