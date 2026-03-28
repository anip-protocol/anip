import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';
import CodeBlock from '@theme/CodeBlock';
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

import styles from './index.module.css';

function HomepageHeader() {
  return (
    <header className={styles.hero}>
      <div className="container">
        <div className={styles.heroInner}>
          <p className={styles.eyebrow}>Agent-Native Interface Protocol</p>
          <Heading as="h1" className={styles.heroTitle}>
            Agents should know what will happen<br />before they act
          </Heading>
          <p className={styles.heroLead}>
            ANIP is an open protocol that makes permissions, side effects, costs,
            and recovery explicit — so AI agents can reason before invoking,
            not discover constraints by failing.
          </p>
          <div className={styles.ctaRow}>
            <Link className="button button--primary button--lg" to="/docs/getting-started/quickstart">
              Get started
            </Link>
            <Link className="button button--outline button--lg" to="/docs/intro">
              Read the docs
            </Link>
          </div>
        </div>
      </div>
    </header>
  );
}

function BeforeAfter() {
  return (
    <section className={styles.section}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <Heading as="h2">The problem ANIP solves</Heading>
          <p>Today's APIs were designed for human developers who read docs and write deterministic code. When agents use them directly, they learn by failing.</p>
        </div>
        <div className={styles.compareGrid}>
          <div className={clsx(styles.compareCard, styles.compareBefore)}>
            <div className={styles.compareLabel}>Without ANIP</div>
            <div className={styles.compareContent}>
              <CodeBlock language="text">{`Agent wants to book a flight
→ Guesses POST /bookings is the right endpoint
→ Discovers auth requirements by getting a 401
→ Discovers missing scope by getting a 403
→ Books the flight
→ Discovers cost was $800 not $420 (undeclared fees)
→ Cannot undo — no rollback info was available
→ No audit trail accessible to the agent`}</CodeBlock>
            </div>
          </div>
          <div className={clsx(styles.compareCard, styles.compareAfter)}>
            <div className={styles.compareLabel}>With ANIP</div>
            <div className={styles.compareContent}>
              <CodeBlock language="text">{`Agent queries manifest
→ Sees book_flight: irreversible, financial
→ Sees cost: ~$420 ±10%, currency: USD
→ Checks delegation chain has travel.book scope
→ Checks budget authority: $500 limit
→ Confirms rollback_window: none (permanent)
→ Decides to proceed with full context
→ Invocation result includes audit trail + lineage`}</CodeBlock>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function HowItWorks() {
  return (
    <section className={clsx(styles.section, styles.sectionAlt)}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <Heading as="h2">How it works</Heading>
          <p>An ANIP service exposes a standard set of endpoints. Agents discover what's available, check permissions, then invoke with full context.</p>
        </div>
        <div className={styles.flowSteps}>
          <div className={styles.flowStep}>
            <div className={styles.flowNumber}>1</div>
            <Heading as="h3">Discover</Heading>
            <p>Agent fetches the discovery document and manifest to learn what capabilities exist, their side effects, costs, and required scopes.</p>
            <CodeBlock language="bash">{`curl https://service.example/.well-known/anip`}</CodeBlock>
          </div>
          <div className={styles.flowStep}>
            <div className={styles.flowNumber}>2</div>
            <Heading as="h3">Evaluate</Heading>
            <p>Agent checks permissions before acting. The service tells the agent what's available, restricted, or denied — not after a failed call, but on request.</p>
            <CodeBlock language="json">{`{
  "available": [{ "capability": "search_flights", "scope_match": "travel.search" }],
  "restricted": [{ "capability": "book_flight", "reason": "missing scope", "grantable_by": "human" }],
  "denied": []
}`}</CodeBlock>
          </div>
          <div className={styles.flowStep}>
            <div className={styles.flowNumber}>3</div>
            <Heading as="h3">Invoke</Heading>
            <p>Agent invokes with a scoped delegation token. The response includes structured success or failure with recovery guidance, cost, and lineage identifiers.</p>
            <CodeBlock language="json">{`{
  "success": true,
  "invocation_id": "inv_7f3a2b",
  "result": { "flights": [{ "number": "AA100", "price": 420 }] },
  "cost_actual": { "currency": "USD", "amount": 0 }
}`}</CodeBlock>
          </div>
          <div className={styles.flowStep}>
            <div className={styles.flowNumber}>4</div>
            <Heading as="h3">Verify</Heading>
            <p>Every invocation is audit-logged with signed checkpoints. Agents, operators, and compliance tools can verify what happened, when, and under what authority.</p>
            <CodeBlock language="bash">{`curl -X POST https://service.example/anip/audit \\
  -H "Authorization: Bearer <token>" \\
  -d '{"capability": "search_flights", "limit": 5}'`}</CodeBlock>
          </div>
        </div>
      </div>
    </section>
  );
}

function QuickStart() {
  const pythonExample = `from fastapi import FastAPI
from anip_service import ANIPService, Capability
from anip_fastapi import mount_anip

service = ANIPService(
    service_id="my-service",
    capabilities=[
        Capability(
            name="search_flights",
            description="Search available flights",
            side_effect="read",
            scope=["travel.search"],
            handler=lambda ctx, params: {
                "flights": [{"number": "AA100", "price": 420}]
            },
        ),
    ],
    authenticate=lambda bearer: {
        "demo-key": "human:demo@example.com"
    }.get(bearer),
)

app = FastAPI()
mount_anip(app, service)`;

  const typescriptExample = `import { Hono } from "hono";
import { createANIPService, defineCapability } from "@anip/service";
import { mountAnip } from "@anip/hono";

const searchFlights = defineCapability({
  name: "search_flights",
  description: "Search available flights",
  sideEffect: "read",
  scope: ["travel.search"],
  handler: async (ctx, params) => ({
    flights: [{ number: "AA100", price: 420 }],
  }),
});

const service = createANIPService({
  serviceId: "my-service",
  capabilities: [searchFlights],
  trust: "signed",
  authenticate: (bearer) =>
    ({ "demo-key": "human:demo@example.com" })[bearer] ?? null,
});

const app = new Hono();
mountAnip(app, service);`;

  const goExample = `package main

import (
    "net/http"
    "github.com/anip-protocol/anip/packages/go/service"
    "github.com/anip-protocol/anip/packages/go/httpapi"
)

func main() {
    svc, _ := service.New(service.Config{
        ServiceID:    "my-service",
        Capabilities: []service.CapabilityDef{searchFlights()},
        Storage:      "sqlite:///anip.db",
        Trust:        "signed",
        Authenticate: func(bearer string) *string {
            keys := map[string]string{
                "demo-key": "human:demo@example.com",
            }
            if p, ok := keys[bearer]; ok { return &p }
            return nil
        },
    })
    defer svc.Shutdown()
    svc.Start()

    mux := http.NewServeMux()
    httpapi.MountANIP(mux, svc)
    http.ListenAndServe(":9100", mux)
}`;

  const javaExample = `@SpringBootApplication
public class Application {
    @Bean
    public ANIPService anipService() {
        return new ANIPService(new ServiceConfig()
            .setServiceId("my-service")
            .setCapabilities(List.of(
                SearchFlightsCapability.create()
            ))
            .setStorage("sqlite:///anip.db")
            .setTrust("signed")
            .setAuthenticate(bearer -> {
                Map<String, String> keys = Map.of(
                    "demo-key", "human:demo@example.com"
                );
                return Optional.ofNullable(keys.get(bearer));
            }));
    }

    @Bean
    public AnipController anipController(ANIPService s) {
        return new AnipController(s);
    }
}`;

  const csharpExample = `var builder = WebApplication.CreateBuilder(args);

var service = new AnipService(new ServiceConfig {
    ServiceId = "my-service",
    Capabilities = [SearchFlightsCapability.Create()],
    Storage = "sqlite:///anip.db",
    Trust = "signed",
    Authenticate = bearer => {
        var keys = new Dictionary<string, string> {
            ["demo-key"] = "human:demo@example.com"
        };
        return keys.TryGetValue(bearer, out var p) ? p : null;
    }
});

builder.Services.AddAnip(service);
var app = builder.Build();
app.MapControllers();
app.Run();`;

  return (
    <section className={styles.section}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <Heading as="h2">Build an ANIP service in minutes</Heading>
          <p>You write business logic. The runtime handles discovery, JWT tokens, signed manifests, delegation validation, audit logging, and Merkle checkpoints.</p>
        </div>
        <Tabs groupId="language" queryString>
          <TabItem value="python" label="Python" default>
            <CodeBlock language="python" title="app.py">{pythonExample}</CodeBlock>
          </TabItem>
          <TabItem value="typescript" label="TypeScript">
            <CodeBlock language="typescript" title="app.ts">{typescriptExample}</CodeBlock>
          </TabItem>
          <TabItem value="go" label="Go">
            <CodeBlock language="go" title="main.go">{goExample}</CodeBlock>
          </TabItem>
          <TabItem value="java" label="Java">
            <CodeBlock language="java" title="Application.java">{javaExample}</CodeBlock>
          </TabItem>
          <TabItem value="csharp" label="C#">
            <CodeBlock language="csharp" title="Program.cs">{csharpExample}</CodeBlock>
          </TabItem>
        </Tabs>
        <div className={styles.codeMeta}>
          <p>Same result in every language — 9 protocol endpoints, signed manifest, delegation-based auth, structured failures, and a verifiable audit log.</p>
          <Link className="button button--primary" to="/docs/getting-started/quickstart">
            Follow the quickstart
          </Link>
        </div>
      </div>
    </section>
  );
}

function WhatShips() {
  return (
    <section className={clsx(styles.section, styles.sectionAlt)}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <Heading as="h2">What ships today</Heading>
          <p>ANIP is not a spec waiting for implementations. It ships working runtimes, tools, and examples across five languages.</p>
        </div>
        <div className={styles.featureGrid}>
          <div className={styles.featureCard}>
            <Heading as="h3">5 runtimes</Heading>
            <p>TypeScript, Python, Java, Go, and C#. Each runtime handles the full protocol — discovery, delegation, audit, checkpoints — so you only write capabilities.</p>
          </div>
          <div className={styles.featureCard}>
            <Heading as="h3">3 transports</Heading>
            <p>HTTP (all runtimes), stdio via JSON-RPC 2.0 (all runtimes), and gRPC via shared proto (Python + Go). Same capabilities, multiple wire formats.</p>
          </div>
          <div className={styles.featureCard}>
            <Heading as="h3">Interface adapters</Heading>
            <p>Mount REST (auto-generated OpenAPI + Swagger), GraphQL (auto-generated SDL), and MCP (Streamable HTTP) alongside native ANIP on the same service.</p>
          </div>
          <div className={styles.featureCard}>
            <Heading as="h3">ANIP Studio</Heading>
            <p>Inspection and invocation UI. Connect to any ANIP service, browse capabilities, check permissions, invoke with structured failure display. Embedded or standalone Docker.</p>
          </div>
          <div className={styles.featureCard}>
            <Heading as="h3">Testing tools</Heading>
            <p>Conformance suite validates protocol compliance. Contract testing verifies declared side effects match observed behavior. Both run against any runtime.</p>
          </div>
          <div className={styles.featureCard}>
            <Heading as="h3">Showcase apps</Heading>
            <p>Travel booking, financial operations, and DevOps infrastructure — three full ANIP services demonstrating real-world patterns with all interfaces mounted.</p>
          </div>
        </div>
      </div>
    </section>
  );
}

function Comparison() {
  return (
    <section className={styles.section}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <Heading as="h2">How ANIP compares</Heading>
          <p>ANIP is not a replacement for HTTP, gRPC, or MCP. It adds the execution context layer that those protocols don't provide.</p>
        </div>
        <div className={styles.tableWrapper}>
          <table className={styles.compareTable}>
            <thead>
              <tr>
                <th>Capability</th>
                <th>REST / OpenAPI</th>
                <th>MCP</th>
                <th>ANIP</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Tool / endpoint discovery</td>
                <td>OpenAPI spec</td>
                <td>Yes</td>
                <td>Yes</td>
              </tr>
              <tr>
                <td>Side-effect declaration</td>
                <td>No</td>
                <td>No</td>
                <td>read / write / transactional / irreversible</td>
              </tr>
              <tr>
                <td>Permission discovery before invoke</td>
                <td>No</td>
                <td>No</td>
                <td>available / restricted / denied</td>
              </tr>
              <tr>
                <td>Scoped delegation (not just auth)</td>
                <td>No</td>
                <td>No</td>
                <td>JWT delegation chains with scope + budget</td>
              </tr>
              <tr>
                <td>Cost declaration + actual cost</td>
                <td>No</td>
                <td>No</td>
                <td>Declared range + actual returned</td>
              </tr>
              <tr>
                <td>Structured failure + recovery</td>
                <td>HTTP status codes</td>
                <td>Error codes</td>
                <td>Type, detail, resolution, grantable_by, retry</td>
              </tr>
              <tr>
                <td>Audit logging</td>
                <td>App-specific</td>
                <td>No</td>
                <td>Protocol-level with retention + classification</td>
              </tr>
              <tr>
                <td>Signed manifests + checkpoints</td>
                <td>No</td>
                <td>No</td>
                <td>JWKS + Merkle checkpoints</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

export default function Home(): ReactNode {
  return (
    <Layout
      title="Agents should know what will happen before they act"
      description="ANIP is an open protocol that makes permissions, side effects, costs, and recovery explicit — so AI agents can reason before invoking.">
      <HomepageHeader />
      <main>
        <BeforeAfter />
        <HowItWorks />
        <QuickStart />
        <WhatShips />
        <Comparison />
      </main>
    </Layout>
  );
}
