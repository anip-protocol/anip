/**
 * Quick integration test — verify the bridge discovers and translates correctly.
 * Run: npx tsx test-bridge.ts [url]
 */

import { discoverService } from "./src/discovery.js";
import { ANIPInvoker } from "./src/invocation.js";
import { capabilityToInputSchema, enrichDescription } from "./src/translation.js";

const url = process.argv[2] ?? "http://localhost:9100";

async function test() {
  console.log(`Testing bridge against ${url}\n`);

  // 1. Discovery
  console.log("1. Discovering service...");
  const service = await discoverService(url);
  console.log(`   Protocol: ${service.protocol}`);
  console.log(`   Compliance: ${service.compliance}`);
  console.log(`   Capabilities: ${Array.from(service.capabilities.keys()).join(", ")}`);

  // 2. Translation
  console.log("\n2. Translating capabilities to MCP tools...");
  for (const [name, cap] of service.capabilities) {
    const schema = capabilityToInputSchema(cap);
    const desc = enrichDescription(cap);
    console.log(`\n   Tool: ${name}`);
    console.log(`   Description: ${desc}`);
    console.log(`   Input properties: ${Object.keys(schema.properties).join(", ")}`);
    console.log(`   Required: ${(schema.required ?? []).join(", ")}`);
  }

  // 3. Invocation
  console.log("\n3. Testing invocation...");
  const invoker = new ANIPInvoker(service, {
    scope: ["travel.search", "travel.book:max_$500"],
    apiKey: "demo-human-key",
  });
  console.log("   Invoker ready");

  const searchResult = await invoker.invoke("search_flights", {
    origin: "SEA",
    destination: "SFO",
    date: "2026-03-10",
  });
  console.log(`\n   search_flights result:\n   ${searchResult.slice(0, 200)}...`);

  const bookResult = await invoker.invoke("book_flight", {
    flight_number: "AA100",
    date: "2026-03-10",
    passengers: 1,
  });
  console.log(`\n   book_flight result:\n   ${bookResult.slice(0, 300)}`);

  console.log("\n--- All tests passed ---");
}

test().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
