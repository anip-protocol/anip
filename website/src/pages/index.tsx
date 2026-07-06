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
          <p className={styles.eyebrow}>The missing layer between reasoning and execution</p>
          <Heading as="h1" className={styles.heroTitle}>
            Agents need service-owned interfaces,<br />not UI recipes in prompts
          </Heading>
          <p className={styles.heroLead}>
            GUIs used to stitch primitive APIs into safe human workflows. MCP exposes
            callable tools, but it does not replace those service-owned workflows by
            itself. Without a governed agent interface, behavior moves into consumer-side
            skills, recipes, and prompts — exactly where hallucinations and prompt
            injection can override it. ANIP moves that behavior back to the service side:
            bounded capabilities, authority, approval, side effects, audit, and recovery
            before execution.
          </p>
          <p className={styles.heroSubLead}>
            ANIP started as a protocol. It is now a complete ecosystem: Studio for
            authoring and review, Registry for signed distribution, CLI generation,
            conformance suites, templates, showcase systems, and verification workflows.
          </p>
          <div className={styles.ctaRow}>
            <Link className="button button--primary button--lg" to="https://github.com/anip-protocol/anip/releases">
              Download Desktop Studio
            </Link>
            <Link className="button button--outline button--lg" to="/docs/showcases/gtm-agent/overview">
              Try the GTM Agent
            </Link>
          </div>
        </div>
      </div>
    </header>
  );
}

function ExperienceANIP() {
  return (
    <section className={clsx(styles.section, styles.experienceSection)}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <Heading as="h2">Experience ANIP before reading the whole spec.</Heading>
          <p>
            Start with something concrete: run a governed agent, inspect a reviewed
            Studio project, or generate services from a signed package. The protocol
            details matter, but the first impression should be executable.
          </p>
        </div>

        <div className={styles.experienceGrid}>
          <div className={styles.experienceCard}>
            <div className={styles.experienceKicker}>5 minutes</div>
            <Heading as="h3">Run the GTM Agent Desktop showcase</Heading>
            <p>
              Ask GTM questions, see bounded answers, approval stops, masking, denial,
              and audit-oriented outputs without installing Docker.
            </p>
            <Link to="/docs/showcases/gtm-agent/overview">Open the GTM showcase docs</Link>
          </div>
          <div className={styles.experienceCard}>
            <div className={styles.experienceKicker}>10-15 minutes</div>
            <Heading as="h3">Open ANIP Studio Desktop</Heading>
            <p>
              Inspect how Product Design and Developer Design become a packageable,
              verifiable capability contract that agents can consume safely.
            </p>
            <Link to="https://github.com/anip-protocol/anip/releases">Download desktop builds</Link>
          </div>
          <div className={styles.experienceCard}>
            <div className={styles.experienceKicker}>15 minutes</div>
            <Heading as="h3">Generate from the Registry</Heading>
            <p>
              Browse signed packages and starter templates, verify a package, lock it,
              and generate a service in Python, TypeScript, Go, Java, or C#.
            </p>
            <Link to="https://registry.anip.dev/registry/packages">Browse the Registry</Link>
          </div>
        </div>

        <div className={styles.pathPanel}>
          <Heading as="h3">Choose your path</Heading>
          <div className={styles.pathGrid}>
            <Link className={styles.pathCard} to="/docs/showcases/overview">
              <span>I want to see what ANIP can do</span>
              <small>Showcases, GTM Agent, and governed fronting apps.</small>
            </Link>
            <Link className={styles.pathCard} to="/docs/getting-started/first-10-minutes">
              <span>I want to build something quickly</span>
              <small>Start small, generate a service, then inspect the contract.</small>
            </Link>
            <Link className={styles.pathCard} to="/docs/studio/overview">
              <span>I want to design capabilities visually</span>
              <small>Studio for PM/business intent, developer evidence, and package review.</small>
            </Link>
            <Link className={styles.pathCard} to="/docs/intro">
              <span>I want the technical details</span>
              <small>Protocol, lifecycle, transports, trust, and generated runtimes.</small>
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

function TheProblem() {
  return (
    <section className={styles.section}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <Heading as="h2">MCP exposes tools. It does not replace product workflows.</Heading>
          <p>
            Today, teams often hand agents raw tools and then teach safe usage with
            prompt text, skills, recipes, and framework glue. That puts the workflow on
            the consumer side instead of the service side. The result is fragile:
            cost is unclear, permissions are implicit, side effects are hidden, approval
            is bolted on afterward, and failure recovery depends on model behavior.
          </p>
        </div>
        <div className={styles.compareGrid}>
          <div className={clsx(styles.compareCard, styles.compareBefore)}>
            <div className={styles.compareLabel}>Tool-first model</div>
            <div className={styles.compareContent}>
              <CodeBlock language="text">{`user intent → prompt/skill recipe → raw tool call

Agent must infer the workflow the UI used to own

Safety rules live in client prompts or skill files

Prompt injection can redirect or bypass guidance

Service sees an API call, not a governed action`}</CodeBlock>
            </div>
          </div>
          <div className={clsx(styles.compareCard, styles.compareAfter)}>
            <div className={styles.compareLabel}>ANIP model</div>
            <div className={styles.compareContent}>
              <CodeBlock language="text">{`user intent → governed capability → safe outcome

Service exposes the workflow as a contract

Agent gets bounded inputs, authority, and outcomes

Approval, denial, audit, and recovery are service-owned

The interface is designed for agents that act`}</CodeBlock>
            </div>
          </div>
        </div>
        <div className={styles.compensationCallout}>
          <Heading as="h3">Framework workflows help, but they do not move the boundary</Heading>
          <p>
            Agent frameworks, workflow graphs, skills, and recipe repositories can make one
            app safer. But the rules still live on the consumer side, are not portable
            across clients, and can force the model to reason through more policy on every
            request. ANIP moves the governed workflow into the service contract, narrowing
            the action space so smaller, cheaper models can safely operate bounded
            capabilities.
          </p>
        </div>
      </div>
    </section>
  );
}

function TheGap() {
  return (
    <section className={clsx(styles.section, styles.sectionAlt)}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <Heading as="h2">The gap</Heading>
          <p>
            APIs and tool protocols help agents find and call systems. They still do not, by themselves,
            define the governed meaning of an action.
          </p>
        </div>
        <div className={styles.gapGrid}>
          <div className={styles.gapCard}>
            <Heading as="h3">What APIs and MCP-style tools expose</Heading>
            <ul>
              <li>Available operations or tools</li>
              <li>Tool names, descriptions, and input schemas</li>
              <li>Transport and authentication shape</li>
            </ul>
          </div>
          <div className={styles.gapCard}>
            <Heading as="h3">What governed agents still need</Heading>
            <ul>
              <li>Which <strong>capability</strong> matches the business intent?</li>
              <li>What does this action <strong>cost</strong>?</li>
              <li>Is it <strong>reversible</strong>?</li>
              <li>Am I <strong>authorized</strong> to do this?</li>
              <li>What are the <strong>side effects</strong>?</li>
              <li>What do I do if I'm <strong>blocked</strong>?</li>
            </ul>
          </div>
        </div>
        <p className={styles.gapCaption}>
          MCP is valuable because it standardizes tool discovery and invocation. ANIP adds the service-side
          governed contract for allowed behavior, authority, approvals, denial, audit, and safe recovery.
        </p>
      </div>
    </section>
  );
}

function AlignmentLayer() {
  return (
    <section className={styles.section}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <Heading as="h2">ANIP aligns product intent with executable capability contracts.</Heading>
          <p>
            Agent safety is not only a runtime problem. PM, business, security, and
            developers need to agree on what capabilities mean before those capabilities
            are exposed to agents. ANIP makes that agreement explicit and verifiable.
          </p>
        </div>
        <div className={styles.alignmentGrid}>
          <div className={styles.alignmentCard}>
            <Heading as="h3">Business defines intent</Heading>
            <p>
              Studio captures scenarios, actors, allowed outcomes, approval boundaries,
              denial rules, and non-happy paths in business language.
            </p>
          </div>
          <div className={styles.alignmentCard}>
            <Heading as="h3">Developers make it enforceable</Heading>
            <p>
              Developer Design turns that intent into capabilities, inputs, input
              resolution, scopes, side effects, backend seams, and validation coverage.
            </p>
          </div>
          <div className={styles.alignmentCard}>
            <Heading as="h3">Consumers verify what shipped</Heading>
            <p>
              Registry packages, signatures, locks, receipts, audit, checkpoints, and
              scenario validation let teams prove the running service matches the
              reviewed contract.
            </p>
          </div>
        </div>
        <p className={styles.alignmentCaption}>
          This is the missing collaboration layer: not just “can the agent call a tool,”
          but “did the service owner publish the behavior the business approved and the
          developer implemented?”
        </p>
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
          <p>
            ANIP is not just a tool catalog. A service exposes governed capabilities with
            authority, input-resolution, approval, failure, audit, and verification semantics.
          </p>
        </div>
        <div className={styles.flowSteps}>
          <div className={styles.flowStep}>
            <div className={styles.flowNumber}>1</div>
            <Heading as="h3">Discover Contract</Heading>
            <p>Agent fetches the discovery document and manifest to learn the service identity, capabilities, side effects, costs, scopes, supported transports, and trust posture.</p>
            <CodeBlock language="bash">{`curl https://service.example/.well-known/anip`}</CodeBlock>
          </div>
          <div className={styles.flowStep}>
            <div className={styles.flowNumber}>2</div>
            <Heading as="h3">Resolve Intent</Heading>
            <p>Agent maps the user request to a governed capability, then follows declared input-resolution rules: clarify, use defaults, use actor scope, resolve references, or stop.</p>
            <CodeBlock language="json">{`{
  "capability": "jira.issue.prepare_bug",
  "input": "severity",
  "resolution": { "mode": "closed_values", "on_missing": "clarify" }
}`}</CodeBlock>
          </div>
          <div className={styles.flowStep}>
            <div className={styles.flowNumber}>3</div>
            <Heading as="h3">Check Authority</Heading>
            <p>Agent checks permission posture before acting. The service says what is available, restricted, denied, or grantable for the current actor and purpose.</p>
            <CodeBlock language="json">{`{
  "available": [{ "capability": "search_flights", "scope_match": "travel.search" }],
  "restricted": [{ "capability": "book_flight", "reason": "missing scope", "grantable_by": "human" }],
  "denied": []
}`}</CodeBlock>
          </div>
          <div className={styles.flowStep}>
            <div className={styles.flowNumber}>4</div>
            <Heading as="h3">Prepare Or Approve</Heading>
            <p>For consequential actions, the service can return a preview or approval request instead of executing. Approval is a contract outcome, not prompt etiquette.</p>
            <CodeBlock language="json">{`{
  "success": false,
  "failure": {
    "type": "approval_required",
    "approval_request_id": "apr_9c21",
    "preview": { "summary": "Move issue to Done" }
  }
}`}</CodeBlock>
          </div>
          <div className={styles.flowStep}>
            <div className={styles.flowNumber}>5</div>
            <Heading as="h3">Invoke Safely</Heading>
            <p>Agent invokes with a purpose-bound delegation token. The response includes structured success or failure with recovery guidance, cost, and lineage identifiers.</p>
            <CodeBlock language="json">{`{
  "success": true,
  "invocation_id": "inv_7f3a2b",
  "result": { "flights": [{ "number": "AA100", "price": 420 }] },
  "cost_actual": { "currency": "USD", "amount": 0 }
}`}</CodeBlock>
          </div>
          <div className={styles.flowStep}>
            <div className={styles.flowNumber}>6</div>
            <Heading as="h3">Verify</Heading>
            <p>Every invocation can be audited and checked against signed packages, locks, receipts, and checkpoints. Consumers can verify what ran, under what authority, and against which contract.</p>
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
import { createANIPService, defineCapability } from "@anip-dev/service";
import { mountAnip } from "@anip-dev/hono";

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
          <Heading as="h2">Build or generate an ANIP service</Heading>
          <p>
            Start from Studio, a signed Registry package, or code. The toolchain keeps the
            contract, generated service shape, verifier checks, and runtime behavior aligned.
          </p>
        </div>

        <div className={styles.buildPathGrid}>
          <div className={styles.buildPathCard}>
            <Heading as="h3">Studio-first</Heading>
            <p>Design capabilities, scenarios, approvals, and fronting contracts in ANIP Studio, then publish a reviewed package or starter template.</p>
          </div>
          <div className={styles.buildPathCard}>
            <Heading as="h3">Package-first</Heading>
            <p>Pull a signed package from the Registry, verify it, lock it, and generate a service in Python, TypeScript, Go, Java, or C#.</p>
          </div>
          <div className={styles.buildPathCard}>
            <Heading as="h3">Code-first</Heading>
            <p>Mount a runtime directly when you already know the capability surface. The runtime handles discovery, delegation, audit, and checkpoints.</p>
          </div>
        </div>

        <div className={styles.codeIntro}>
          <Heading as="h3">Code-first runtime example</Heading>
          <p>The same contract can also be implemented manually when you want direct control over the service code.</p>
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
          <p>Same result in every language: governed discovery, signed manifest, delegation-based auth, structured failures, approval/audit surfaces, and verifiable checkpoints.</p>
          <CodeBlock language="bash">{`anip verify --package-bundle ./service.anip-package.json
anip generate --package-bundle ./service.anip-package.json --target typescript --output ./generated/service`}</CodeBlock>
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
          <p>
            ANIP is not a spec waiting for implementations. It ships runtimes,
            Studio, Registry, CLI tooling, package workflows, and showcase systems.
          </p>
        </div>
        <div className={styles.featureGrid}>
          <div className={styles.featureCard}>
            <Heading as="h3">5 runtimes</Heading>
            <p>TypeScript, Python, Java, Go, and C#. Each runtime handles the full protocol — discovery, delegation, audit, checkpoints — so you only write capabilities.</p>
          </div>
          <div className={styles.featureCard}>
            <Heading as="h3">ANIP CLI</Heading>
            <p>Generate services, verify definitions and packages, publish package revisions, emit locks, and create integration templates from the command line.</p>
          </div>
          <div className={styles.featureCard}>
            <Heading as="h3">ANIP Registry</Heading>
            <p>Signed packages, templates, locks, contract signatures, tooling metadata, download tracking, and consumer-facing package guidance. <a href="https://registry.anip.dev/registry/packages" target="_blank" rel="noopener">Browse packages</a>.</p>
          </div>
          <div className={styles.featureCard}>
            <Heading as="h3">ANIP Studio</Heading>
            <p>Guided and Autopilot project design, fronting flows, source docs, product/developer revisions, diagnostics, package publication, and template export.</p>
          </div>
          <div className={styles.featureCard}>
            <Heading as="h3">Transports and interfaces</Heading>
            <p>HTTP, stdio JSON-RPC, and gRPC support, plus generated inbound surfaces such as OpenAPI/REST, GraphQL, and MCP compatibility where useful.</p>
          </div>
          <div className={styles.featureCard}>
            <Heading as="h3">Conformance and validation</Heading>
            <p>Runtime conformance, generator conformance, package verification, scenario-driven execution design, and execution scenario validation.</p>
          </div>
          <div className={styles.featureCard}>
            <Heading as="h3">GTM Agent showcase</Heading>
            <p>A full GTM agent system with generated ANIP services in all five languages, approval flows, question banks, local Docker stacks, and Metabase verification.</p>
          </div>
          <div className={styles.featureCard}>
            <Heading as="h3">Fronting showcases</Heading>
            <p>Governed fronting packages for Jira, GitHub, GitLab, Slack, Linear, Notion, and Superset-style analytics. The point is capabilities, not raw API mimicry.</p>
          </div>
          <div className={styles.featureCard}>
            <Heading as="h3">Starter templates</Heading>
            <p>Reusable project templates for Studio so teams can start from reviewed structures instead of recreating every service or fronting project from scratch.</p>
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
          <p>
            ANIP is not a replacement for HTTP, gRPC, or MCP. It adds a governed
            execution contract above transport, tool discovery, and tool-call schemas.
          </p>
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
                <td>Endpoint catalog</td>
                <td>Tool catalog</td>
                <td><Link to="/docs/protocol/reference#discovery">Signed capability contract</Link></td>
              </tr>
              <tr>
                <td>Side-effect posture</td>
                <td>Usually inferred or documented in prose</td>
                <td>Advisory hints clients may use</td>
                <td><Link to="/docs/protocol/capabilities#side-effect-types">Contract posture used by permission, approval, audit, and verification</Link></td>
              </tr>
              <tr>
                <td>Permission discovery before invoke</td>
                <td>Usually learn by calling and failing</td>
                <td>Usually host/server-specific policy</td>
                <td><Link to="/docs/protocol/delegation-permissions#permission-discovery">Portable available / restricted / denied posture before execution</Link></td>
              </tr>
              <tr>
                <td>Scoped delegation and purpose limits</td>
                <td>External auth; execution purpose is app-defined</td>
                <td>Transport auth; execution purpose is not a portable contract</td>
                <td><Link to="/docs/protocol/authentication">Purpose-bound delegation chains with scope and budget narrowing</Link></td>
              </tr>
              <tr>
                <td>Input resolution and clarification</td>
                <td>Validation only; clarification is app logic</td>
                <td>Tool schema and client/server behavior</td>
                <td><Link to="/docs/protocol/reference#input-resolution-v024">Declared clarify / default / actor-scope / resolver behavior</Link></td>
              </tr>
              <tr>
                <td>Approval and preview outcomes</td>
                <td>Possible, but custom</td>
                <td>Possible, but host/tool-specific</td>
                <td><Link to="/docs/protocol/failures-cost-audit#approval-required-failures">Standard approval_required outcome with grant continuation</Link></td>
              </tr>
              <tr>
                <td>Cost declaration + actual cost</td>
                <td>Custom if needed</td>
                <td>No portable cost contract</td>
                <td><Link to="/docs/protocol/capabilities#cost-declaration">Declared estimate before execution + actual cost after execution</Link></td>
              </tr>
              <tr>
                <td>Structured failure + recovery</td>
                <td>Status codes plus custom error bodies</td>
                <td>Tool errors plus custom payloads</td>
                <td><Link to="/docs/protocol/failures-cost-audit#structured-failures">Portable failure type, recovery action, grantability, and retry guidance</Link></td>
              </tr>
              <tr>
                <td>Audit logging</td>
                <td>Custom logs</td>
                <td>Host/server logs</td>
                <td><Link to="/docs/protocol/failures-cost-audit#audit-logging">Protocol audit trail with retention, classification, lineage, and authority context</Link></td>
              </tr>
              <tr>
                <td>Package verification and execution evidence</td>
                <td>External supply-chain tooling</td>
                <td>Implementation-specific</td>
                <td><Link to="/docs/protocol/checkpoints-trust">Signed packages, locks, receipts, JWKS, and tamper-evident checkpoints</Link></td>
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
      title="The missing layer between reasoning and execution"
      description="ANIP is the control layer that makes cost, authority, side effects, and recovery explicit before an agent executes.">
      <HomepageHeader />
      <main>
        <ExperienceANIP />
        <TheProblem />
        <TheGap />
        <AlignmentLayer />
        <HowItWorks />
        <QuickStart />
        <WhatShips />
        <Comparison />
      </main>
    </Layout>
  );
}
