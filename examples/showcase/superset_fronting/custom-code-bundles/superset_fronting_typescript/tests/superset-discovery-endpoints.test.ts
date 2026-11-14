import { describe, expect, it } from "vitest";
import { discoveryEndpoints } from "../src/runtime/backend-adapter.js";

const kinds = (assetType: string) => discoveryEndpoints(assetType).map(([kind]) => kind);

describe("Superset discovery endpoints", () => {
  // "all" is asset_type's declared default, so it is what a call without
  // asset_type carries; it must not filter out every endpoint.
  it("reads every catalog for all and for an empty asset_type", () => {
    expect(kinds("all")).toEqual(["dataset", "chart", "dashboard"]);
    expect(kinds("")).toEqual(["dataset", "chart", "dashboard"]);
  });

  it("reads the one catalog of a named kind", () => {
    expect(kinds("chart")).toEqual(["chart"]);
    // metric and dimension are declared values without a Superset list endpoint.
    expect(kinds("metric")).toEqual([]);
  });
});
