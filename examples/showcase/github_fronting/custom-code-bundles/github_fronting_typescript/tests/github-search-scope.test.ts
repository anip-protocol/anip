import { afterEach, describe, expect, it } from "vitest";
import { backendAdapter, itemInRepo, queryWidensScope } from "../src/runtime/backend-adapter.js";

const plan = {
  selected_binding: null,
  semantic_input: {},
  adapter_input: {},
  backend_input_contract: { mode: "explicit", required: [], optional: [] },
  unresolved_required_backend_inputs: [],
} as any;

describe("GitHub search scope", () => {
  const previousToken = process.env.GITHUB_TOKEN;
  afterEach(() => {
    if (previousToken === undefined) delete process.env.GITHUB_TOKEN;
    else process.env.GITHUB_TOKEN = previousToken;
  });

  it("refuses a query carrying repo:, org:, user: or owner: qualifiers", async () => {
    process.env.GITHUB_TOKEN = "token";
    for (const query of ["repo:other/private", "bug REPO:other/private", "org:acme-private", "user: someone", "owner :someone"]) {
      const result = await backendAdapter.execute({ capability_id: "github.repo.search_context" } as any, plan, { owner: "acme", repo: "demo", query }, {});
      expect(result.execution_status).toBe("restricted");
    }
    expect(queryWidensScope("label:bug repository crash")).toBe(false);
  });

  it("keeps only items from the requested repository", () => {
    expect(itemInRepo({ repository_url: "https://api.github.com/repos/Acme/Demo" }, "acme", "demo")).toBe(true);
    expect(itemInRepo({ repository_url: "https://api.github.com/repos/other/private" }, "acme", "demo")).toBe(false);
    expect(itemInRepo({ repository_url: "https://api.github.com/repos/acme/demo-fork" }, "acme", "demo")).toBe(false);
    expect(itemInRepo({}, "acme", "demo")).toBe(false);
  });
});
