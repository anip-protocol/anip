/**
 * The HTTP status of each failure type in the flight example
 * (SPEC.md §6.3 "HTTP Status Codes").
 */
import { describe, it, expect } from "vitest";
import { app } from "../src/app.js";

async function issue(capability: string, scope: string[], extra: Record<string, unknown> = {}) {
  const res = await app.request("/anip/tokens", {
    method: "POST",
    headers: { "Authorization": "Bearer demo-human-key", "Content-Type": "application/json" },
    body: JSON.stringify({ subject: "human:samir@example.com", scope, capability, ...extra }),
  });
  expect(res.status).toBe(200);
  return (await res.json()) as { token: string; token_id: string };
}

async function post(path: string, bearer: string | null, body: string) {
  const res = await app.request(path, {
    method: "POST",
    headers: {
      ...(bearer === null ? {} : { "Authorization": `Bearer ${bearer}` }),
      "Content-Type": "application/json",
    },
    body,
  });
  return { status: res.status, data: await res.json() };
}

const now = () => Math.floor(Date.now() / 1000);

function booking(quote: Record<string, unknown> | null): string {
  return JSON.stringify({
    parameters: { flight_number: "AA100", date: "2026-03-10", passengers: 1, ...(quote ? { quote_id: quote } : {}) },
  });
}

describe("HTTP status per failure type", () => {
  it("binding_missing and binding_stale are 403", async () => {
    const { token } = await issue("book_flight", ["travel.book"]);

    const missing = await post("/anip/invoke/book_flight", token, booking(null));
    expect(missing.data.failure.type).toBe("binding_missing");
    expect(missing.status).toBe(403);

    const stale = await post(
      "/anip/invoke/book_flight", token, booking({ id: "qt-old", price: 420, issued_at: now() - 3600 }));
    expect(stale.data.failure.type).toBe("binding_stale");
    expect(stale.status).toBe(403);
  });

  it("budget_exceeded, budget_currency_mismatch and budget_not_enforceable are 403", async () => {
    const quote = { id: "qt-test-1234", price: 420, issued_at: now() };
    const small = await issue("book_flight", ["travel.book"], { budget: { currency: "USD", max_amount: 100 } });

    const exceeded = await post("/anip/invoke/book_flight", small.token, booking(quote));
    expect(exceeded.data.failure.type).toBe("budget_exceeded");
    expect(exceeded.status).toBe(403);

    const noPrice = await post(
      "/anip/invoke/book_flight", small.token, booking({ id: "qt-test-1234", issued_at: now() }));
    expect(noPrice.data.failure.type).toBe("budget_not_enforceable");
    expect(noPrice.status).toBe(403);

    const eur = await issue("book_flight", ["travel.book"], { budget: { currency: "EUR", max_amount: 1000 } });
    const mismatch = await post("/anip/invoke/book_flight", eur.token, booking(quote));
    expect(mismatch.data.failure.type).toBe("budget_currency_mismatch");
    expect(mismatch.status).toBe(403);
  });

  it("scope_escalation at the token endpoint is 403", async () => {
    const parent = await issue("search_flights", ["travel.search"]);

    const res = await post("/anip/tokens", parent.token, JSON.stringify({
      subject: "agent:child", scope: ["travel.search", "travel.book"], capability: "search_flights",
      parent_token: parent.token_id,
    }));

    expect(res.data.failure.type).toBe("scope_escalation");
    expect(res.status).toBe(403);
  });

  it("a spent one_time grant is grant_consumed, 409", async () => {
    const { token } = await issue("book_flight", ["travel.book"]);
    const approver = await issue("book_flight", ["approver:book_flight"]);
    const parameters = { flight_number: "AA100", date: "2026-03-10", passengers: 5, quote_id: { id: "qt-g", price: 420, issued_at: now() } };

    const first = await post("/anip/invoke/book_flight", token, JSON.stringify({ parameters }));
    expect(first.data.failure.type).toBe("approval_required");
    expect(first.status).toBe(400);
    const grant = await post("/anip/approval_grants", approver.token, JSON.stringify({
      approval_request_id: first.data.failure.approval_required.approval_request_id, grant_type: "one_time",
    }));
    expect(grant.status).toBe(200);
    const continuation = JSON.stringify({ parameters, approval_grant: grant.data.grant_id });
    expect((await post("/anip/invoke/book_flight", token, continuation)).status).toBe(200);

    const again = await post("/anip/invoke/book_flight", token, continuation);

    expect(again.data.failure.type).toBe("grant_consumed");
    expect(again.status).toBe(409);
  });

  it("a request body that is not JSON is invalid_parameters, 400, after the credential check", async () => {
    const { token } = await issue("search_flights", ["travel.search"]);

    for (const [path, bearer, body] of [
      ["/anip/invoke/search_flights", token, '{"parameters": '],
      ["/anip/tokens", "demo-human-key", '{"scope": '],
    ] as const) {
      const res = await post(path, bearer, body);
      expect(res.status, path).toBe(400);
      expect(res.data.failure.type, path).toBe("invalid_parameters");
      expect(res.data.failure.resolution, path).toMatchObject({ action: "retry_now", recovery_class: "retry_now" });
      expect(res.data.failure.retry, path).toBe(false);

      const none = await post(path, null, body);
      expect(none.status, path).toBe(401);
      expect(none.data.failure.type, path).toBe("authentication_required");
    }
  });
});
