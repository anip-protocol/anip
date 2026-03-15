import { describe, it, expect } from "vitest";
import { app } from "../src/app.js";

describe("Discovery", () => {
  it("GET /.well-known/anip returns capabilities", async () => {
    const res = await app.request("/.well-known/anip");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.anip_discovery.capabilities.search_flights).toBeDefined();
    expect(data.anip_discovery.capabilities.book_flight).toBeDefined();
  });

  it("GET /anip/manifest is signed", async () => {
    const res = await app.request("/anip/manifest");
    expect(res.status).toBe(200);
    expect(res.headers.get("X-ANIP-Signature")).toBeTruthy();
  });

  it("GET /.well-known/jwks.json returns keys", async () => {
    const res = await app.request("/.well-known/jwks.json");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.keys.length).toBeGreaterThan(0);
  });
});

async function getToken(capability = "search_flights", scope = ["travel.search", "travel.book"]) {
  const res = await app.request("/anip/tokens", {
    method: "POST",
    headers: {
      "Authorization": "Bearer demo-human-key",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      subject: "human:samir@example.com",
      scope,
      capability,
      purpose_parameters: { task_id: "test" },
    }),
  });
  const data = await res.json();
  return data.token as string;
}

describe("Tokens", () => {
  it("issues token with API key", async () => {
    const res = await app.request("/anip/tokens", {
      method: "POST",
      headers: {
        "Authorization": "Bearer demo-human-key",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        scope: ["travel.search"],
        capability: "search_flights",
        purpose_parameters: { task_id: "test" },
      }),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.issued).toBe(true);
  });

  it("rejects unauthenticated request", async () => {
    const res = await app.request("/anip/tokens", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope: ["travel.search"] }),
    });
    expect(res.status).toBe(401);
  });
});

describe("Invoke", () => {
  it("searches flights", async () => {
    const token = await getToken("search_flights");
    const res = await app.request("/anip/invoke/search_flights", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        parameters: { origin: "SEA", destination: "SFO", date: "2026-03-10" },
      }),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.success).toBe(true);
    expect(data.result.count).toBe(3);
  });

  it("returns empty for no matching flights", async () => {
    const token = await getToken("search_flights");
    const res = await app.request("/anip/invoke/search_flights", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        parameters: { origin: "SEA", destination: "SFO", date: "2099-01-01" },
      }),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.success).toBe(true);
    expect(data.result.count).toBe(0);
  });

  it("books a flight", async () => {
    const token = await getToken("book_flight");
    const res = await app.request("/anip/invoke/book_flight", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        parameters: { flight_number: "AA100", date: "2026-03-10", passengers: 1 },
      }),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.success).toBe(true);
    expect(data.result.booking_id).toMatch(/^BK-/);
    expect(data.result.total_cost).toBe(420);
  });

  it("rejects unauthenticated invoke", async () => {
    const res = await app.request("/anip/invoke/search_flights", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parameters: { origin: "SEA", destination: "SFO", date: "2026-03-10" } }),
    });
    expect(res.status).toBe(401);
  });

  it("returns 404 for unknown capability", async () => {
    const token = await getToken("search_flights");
    const res = await app.request("/anip/invoke/nonexistent", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ parameters: {} }),
    });
    expect(res.status).toBe(404);
    const data = await res.json();
    expect(data.success).toBe(false);
  });
});

describe("Checkpoints", () => {
  it("lists checkpoints", async () => {
    const res = await app.request("/anip/checkpoints");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.checkpoints).toBeDefined();
  });
});
