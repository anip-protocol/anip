/**
 * Parameter validation in the flight example (SPEC.md §4.1 "Inputs",
 * §6.3 "Parameter Validation"): the runtime refuses a call that does not
 * match the declared inputs before a handler runs.
 */
import { describe, it, expect } from "vitest";
import { app } from "../src/app.js";

const RESOLUTION = {
  action: "retry_now",
  recovery_class: "retry_now",
  requires: "parameters that match the capability's declared inputs",
};

async function tokenFor(capability: string, scope: string[]): Promise<string> {
  const res = await app.request("/anip/tokens", {
    method: "POST",
    headers: { "Authorization": "Bearer demo-human-key", "Content-Type": "application/json" },
    body: JSON.stringify({ subject: "human:samir@example.com", scope, capability }),
  });
  expect(res.status).toBe(200);
  return (await res.json()).token as string;
}

/** POST an invocation; `rawParameters` is the JSON text of the parameters. */
async function invoke(capability: string, token: string, rawParameters: string) {
  const res = await app.request(`/anip/invoke/${capability}`, {
    method: "POST",
    headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
    body: `{"parameters": ${rawParameters}}`,
  });
  return { status: res.status, data: await res.json() };
}

function quote(price = 420): string {
  return JSON.stringify({ id: "qt-test-1234", price, issued_at: Math.floor(Date.now() / 1000) });
}

describe("Declared inputs", () => {
  it("every input states `required`, and book_flight.quote_id is optional", async () => {
    const manifest = await (await app.request("/anip/manifest")).json();
    const required = (capability: string) =>
      Object.fromEntries(
        manifest.capabilities[capability].inputs.map((i: Record<string, unknown>) => [i.name, i.required]),
      );
    expect(required("search_flights")).toEqual({ origin: true, destination: true, date: true });
    // The binding requirement, not `required`, is what demands quote_id.
    expect(required("book_flight")).toEqual({
      flight_number: true, date: true, passengers: false, quote_id: false,
    });
    expect(manifest.capabilities.book_flight.requires_binding[0].field).toBe("quote_id");
  });
});

describe("Parameter validation", () => {
  it("search_flights without its inputs is refused by the runtime", async () => {
    const token = await tokenFor("search_flights", ["travel.search"]);

    const { status, data } = await invoke("search_flights", token, "{}");

    expect(status).toBe(400);
    expect(data.success).toBe(false);
    expect(data.failure).toEqual({
      type: "invalid_parameters",
      detail: "search_flights is missing required input(s): origin, destination, date",
      resolution: RESOLUTION,
      retry: false,
    });
  });

  it("book_flight without a required input is refused by the runtime", async () => {
    const token = await tokenFor("book_flight", ["travel.book"]);

    const { status, data } = await invoke(
      "book_flight", token, `{"flight_number": "AA100", "passengers": 1, "quote_id": ${quote()}}`);

    expect(status).toBe(400);
    expect(data.failure).toEqual({
      type: "invalid_parameters",
      detail: "book_flight is missing required input(s): date",
      resolution: RESOLUTION,
      retry: false,
    });
  });

  it("book_flight with a value of the wrong JSON type is refused by the runtime", async () => {
    const token = await tokenFor("book_flight", ["travel.book"]);

    const { status, data } = await invoke(
      "book_flight", token,
      `{"flight_number": "AA100", "date": "2026-03-10", "passengers": "1", "quote_id": ${quote()}}`);

    expect(status).toBe(400);
    expect(data.failure.type).toBe("invalid_parameters");
    expect(data.failure.detail).toBe("book_flight has invalid input(s): 'passengers' must be integer, got string");
  });

  it("the handler's own invalid_parameters is a complete failure with retry false", async () => {
    const token = await tokenFor("book_flight", ["travel.book"]);

    // An empty string is a string: the runtime lets it through, the handler refuses it.
    const { status, data } = await invoke(
      "book_flight", token, `{"flight_number": "", "date": "2026-03-10", "quote_id": ${quote()}}`);

    expect(status).toBe(400);
    expect(data.failure.type).toBe("invalid_parameters");
    expect(data.failure.detail).toBe("flight_number and date are required");
    expect(data.failure.resolution).toEqual(RESOLUTION);
    expect(data.failure.retry).toBe(false);
  });

  it("book_flight without quote_id is binding_missing, not invalid_parameters", async () => {
    const token = await tokenFor("book_flight", ["travel.book"]);

    const { data } = await invoke("book_flight", token, '{"flight_number": "AA100", "date": "2026-03-10"}');

    expect(data.failure.type).toBe("binding_missing");
  });

  it("optional passengers may be left out", async () => {
    const token = await tokenFor("book_flight", ["travel.book"]);

    const { status, data } = await invoke(
      "book_flight", token, `{"flight_number": "AA100", "date": "2026-03-10", "quote_id": ${quote()}}`);

    expect(status).toBe(200);
    expect(data.result.total_cost).toBe(420);
  });

  it("an integral float is an integer: passengers 1.0 and 2.0 book for that many", async () => {
    const token = await tokenFor("book_flight", ["travel.book"]);

    const one = await invoke(
      "book_flight", token,
      `{"flight_number": "AA100", "date": "2026-03-10", "passengers": 1.0, "quote_id": ${quote()}}`);
    expect(one.status).toBe(200);
    expect(one.data.result.total_cost).toBe(420);

    const two = await invoke(
      "book_flight", token,
      `{"flight_number": "AA100", "date": "2026-03-10", "passengers": 2.0, "quote_id": ${quote()}}`);
    expect(two.status).toBe(200);
    expect(two.data.result.total_cost).toBe(840);
  });

  it("a fractional number of passengers is refused", async () => {
    const token = await tokenFor("book_flight", ["travel.book"]);

    const { status, data } = await invoke(
      "book_flight", token,
      `{"flight_number": "AA100", "date": "2026-03-10", "passengers": 1.5, "quote_id": ${quote()}}`);

    expect(status).toBe(400);
    expect(data.failure.detail).toBe("book_flight has invalid input(s): 'passengers' must be integer, got number");
  });

  it("an approved booking for 5 continues when the continuation writes 5.0", async () => {
    const token = await tokenFor("book_flight", ["travel.book"]);
    const approver = await tokenFor("book_flight", ["approver:book_flight"]);
    const q = quote();
    const parameters = (passengers: string) =>
      `{"flight_number": "AA100", "date": "2026-03-10", "passengers": ${passengers}, "quote_id": ${q}}`;

    const first = await invoke("book_flight", token, parameters("5"));
    expect(first.data.failure.type).toBe("approval_required");
    const requestId = first.data.failure.approval_required.approval_request_id;
    const grantRes = await app.request("/anip/approval_grants", {
      method: "POST",
      headers: { "Authorization": `Bearer ${approver}`, "Content-Type": "application/json" },
      body: JSON.stringify({ approval_request_id: requestId, grant_type: "one_time" }),
    });
    expect(grantRes.status).toBe(200);
    const grantId = (await grantRes.json()).grant_id;

    const res = await app.request("/anip/invoke/book_flight", {
      method: "POST",
      headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
      body: `{"parameters": ${parameters("5.0")}, "approval_grant": "${grantId}"}`,
    });

    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.success).toBe(true);
    expect(data.result.total_cost).toBe(5 * 420);
  });
});
