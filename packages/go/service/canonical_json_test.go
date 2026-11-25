// Canonical JSON for approval digests is RFC 8785 (SPEC.md §4.7). The shared
// vectors in packages/canonical-json-fixtures are run by every runtime.

package service

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"testing"
)

type canonicalVector struct {
	Name             string `json:"name"`
	Input            string `json:"input"`
	Canonical        string `json:"canonical"`
	CanonicalUTF8Hex string `json:"canonical_utf8_hex"`
	SHA256           string `json:"sha256"`
}

func loadCanonicalVectors(t *testing.T) []canonicalVector {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("..", "..", "canonical-json-fixtures", "rfc8785-vectors.json"))
	if err != nil {
		t.Fatalf("read shared vectors: %v", err)
	}
	var doc struct {
		Vectors []canonicalVector `json:"vectors"`
	}
	if err := json.Unmarshal(data, &doc); err != nil {
		t.Fatalf("decode shared vectors: %v", err)
	}
	if len(doc.Vectors) != 65 {
		t.Fatalf("expected the 65 shared vectors, found %d", len(doc.Vectors))
	}
	return doc.Vectors
}

// parseLikeTheHTTPBinding parses a JSON text the way httpapi and ginapi parse
// an invocation body: json.NewDecoder(body).Decode into an untyped value, so
// numbers arrive as float64.
func parseLikeTheHTTPBinding(t *testing.T, text string, useNumber bool) any {
	t.Helper()
	decoder := json.NewDecoder(bytes.NewReader([]byte(text)))
	if useNumber {
		decoder.UseNumber()
	}
	var value any
	if err := decoder.Decode(&value); err != nil {
		t.Fatalf("parse %q: %v", text, err)
	}
	return value
}

func TestCanonicalJSONSharedRFC8785Vectors(t *testing.T) {
	for _, vector := range loadCanonicalVectors(t) {
		// useNumber: a binding configured to decode numbers as json.Number
		// (gin's EnableJsonDecoderUseNumber) must produce the same bytes.
		for _, useNumber := range []bool{false, true} {
			name := vector.Name
			if useNumber {
				name += "/json.Number"
			}
			t.Run(name, func(t *testing.T) {
				value := parseLikeTheHTTPBinding(t, vector.Input, useNumber)

				canonical, err := CanonicalJSON(value)
				if err != nil {
					t.Fatalf("CanonicalJSON: %v", err)
				}
				if got := hex.EncodeToString(canonical); got != vector.CanonicalUTF8Hex {
					t.Fatalf("canonical bytes differ\n  got  %s (%q)\n  want %s (%q)", got, canonical, vector.CanonicalUTF8Hex, vector.Canonical)
				}
				if string(canonical) != vector.Canonical {
					t.Fatalf("canonical = %q, want %q", canonical, vector.Canonical)
				}

				digest, err := Sha256Digest(value)
				if err != nil {
					t.Fatalf("Sha256Digest: %v", err)
				}
				if digest != vector.SHA256 {
					t.Fatalf("digest = %s, want %s", digest, vector.SHA256)
				}
				sum := sha256.Sum256(canonical)
				if "sha256:"+hex.EncodeToString(sum[:]) != digest {
					t.Fatalf("Sha256Digest is not the SHA-256 of the canonical bytes")
				}
			})
		}
	}
}

// Every number is an IEEE 754 double first, whatever Go type carries it.
func TestCanonicalJSONNativeNumbers(t *testing.T) {
	type payload struct {
		Count int     `json:"count"`
		Price float64 `json:"price"`
	}
	cases := []struct {
		name  string
		value any
		want  string
	}{
		{"int", 5, `5`},
		{"negative int", -17, `-17`},
		{"int64 beyond 2^53", int64(9007199254740993), `9007199254740992`},
		{"uint64 max", uint64(math.MaxUint64), `18446744073709552000`},
		{"float32", float32(0.5), `0.5`},
		{"integral float", 5.0, `5`},
		{"negative zero", math.Copysign(0, -1), `0`},
		{"1e21", 1e21, `1e+21`},
		{"just below 1e21", 999999999999999900000.0, `999999999999999900000`},
		{"1e-6", 1e-6, `0.000001`},
		{"1e-7", 1e-7, `1e-7`},
		{"smallest double", math.SmallestNonzeroFloat64, `5e-324`},
		{"largest double", math.MaxFloat64, `1.7976931348623157e+308`},
		{"json.Number", json.Number("5.00"), `5`},
		{"json.Number beyond 2^53", json.Number("9007199254740993"), `9007199254740992`},
		{"struct", payload{Count: 5, Price: 420.0}, `{"count":5,"price":420}`},
		{"map of typed values", map[string]any{"b": []int{2, 1}, "a": map[string]float64{"x": 1.50}}, `{"a":{"x":1.5},"b":[2,1]}`},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, err := CanonicalJSON(tc.value)
			if err != nil {
				t.Fatalf("CanonicalJSON: %v", err)
			}
			if string(got) != tc.want {
				t.Fatalf("CanonicalJSON = %s, want %s", got, tc.want)
			}
		})
	}
}

func TestCanonicalJSONRejectsNonFiniteNumbers(t *testing.T) {
	for name, value := range map[string]any{
		"NaN":         math.NaN(),
		"+Inf":        math.Inf(1),
		"-Inf":        math.Inf(-1),
		"nested NaN":  map[string]any{"a": []any{1.0, math.NaN()}},
		"json.Number": json.Number("1e999"),
	} {
		if got, err := CanonicalJSON(value); err == nil {
			t.Errorf("%s: expected an error, got %s", name, got)
		}
		if _, err := Sha256Digest(value); err == nil {
			t.Errorf("%s: Sha256Digest must fail too", name)
		}
	}
}

// SPEC.md §4.7: "5, 5.0 and 5e0 are the same JSON number and produce the same
// digest"; another number is another digest.
func TestSha256DigestIntegralFloatIsTheSameNumber(t *testing.T) {
	digest := func(text string) string {
		d, err := Sha256Digest(parseLikeTheHTTPBinding(t, text, false))
		if err != nil {
			t.Fatalf("Sha256Digest(%s): %v", text, err)
		}
		return d
	}
	approved := digest(`{"flight_number":"AA100","passengers":5}`)
	for _, same := range []string{
		`{"flight_number":"AA100","passengers":5.0}`,
		`{"passengers":5e0,"flight_number":"AA100"}`,
		`{"passengers":50e-1,  "flight_number":"AA100"}`,
	} {
		if digest(same) != approved {
			t.Errorf("%s must have the digest of passengers: 5", same)
		}
	}
	for _, other := range []string{
		`{"flight_number":"AA100","passengers":6}`,
		`{"flight_number":"AA100","passengers":5.5}`,
		`{"flight_number":"AA100","passengers":"5"}`,
		`{"flight_number":"AA100","passengers":50}`,
	} {
		if digest(other) == approved {
			t.Errorf("%s must not have the digest of passengers: 5", other)
		}
	}
}
