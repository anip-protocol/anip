import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

import styles from './index.module.css';

const HARNESS = 'https://github.com/anip-protocol/mcp-annotation-check';
const REPORT =
  'https://github.com/anip-protocol/mcp-annotation-check/blob/main/results/2026-11-26-github-mcp-server-v2.3.0-round-1.md';
const ISSUE_3760 = 'https://github.com/github/github-mcp-server/issues/3760';
const MAPPING = 'https://github.com/anip-protocol/anip/blob/main/docs/mcp-extension-mapping.md';

function Hero(): ReactNode {
  return (
    <header className={styles.hero}>
      <div className="container">
        <p className={styles.eyebrow}>ANIP · November 2026</p>
        <Heading as="h1" className={styles.title}>
          ANIP&apos;s ideas are moving into MCP
        </Heading>
        <p className={styles.lead}>
          ANIP was a protocol in which a service states, in checkable form, what a call will do,
          who may make it and how to recover when it is refused. The protocol is now frozen to
          security fixes. The work continues as extensions and tooling for the{' '}
          <Link to="https://modelcontextprotocol.io">Model Context Protocol</Link>.
        </p>
        <div className={styles.ctaRow}>
          <Link className="button button--primary button--lg" to={HARNESS}>
            See the harness
          </Link>
          <Link className="button button--outline button--primary button--lg" to={REPORT}>
            Read the first results
          </Link>
        </div>
      </div>
    </header>
  );
}

function Evidence(): ReactNode {
  return (
    <section className={styles.section}>
      <Heading as="h2">First evidence</Heading>
      <p>
        <Link to={HARNESS}>
          <code>mcp-annotation-check</code>
        </Link>{' '}
        calls an MCP server&apos;s tools against known fixtures and compares state before and
        after through a separate channel. It checks whether each tool behaves the way its{' '}
        <code>readOnlyHint</code>, <code>destructiveHint</code> and <code>idempotentHint</code>{' '}
        annotations claim. Run against GitHub&apos;s MCP server v2.3.0, which lists 62 tools:
      </p>
      <ul>
        <li>All 25 read-only claims tested held.</li>
        <li>
          <code>update_issue_labels</code> claims to be non-destructive, but replaced the labels{' '}
          <code>c</code> and <code>d</code> with <code>a</code>. Its own description says it
          replaces the current labels.
        </li>
        <li>
          <code>update_issue_assignees</code> makes the same claim. An empty list removed the
          existing assignee.
        </li>
      </ul>
      <p className={styles.note}>
        One server, one release, one configuration. A pass means no counterexample on these
        fixtures, not proof. The results are posted on{' '}
        <Link to={ISSUE_3760}>github-mcp-server#3760</Link> and in the{' '}
        <Link to={REPORT}>round 1 report</Link>.
      </p>
    </section>
  );
}

function WhyMove(): ReactNode {
  return (
    <section className={styles.section}>
      <Heading as="h2">Why the move</Heading>
      <ul>
        <li>
          <strong>MCP is where agents and tool servers already are.</strong> A separate wire
          protocol asks every client and server to adopt a second one. An MCP extension asks much
          less.
        </li>
        <li>
          <strong>Five runtimes drifted apart.</strong> One person kept Python, TypeScript, Go,
          Java and C# in step, and it did not hold. Three security releases,{' '}
          <Link to="/docs/releases/delegation-enforcement-0-24-18">0.24.18</Link> to{' '}
          <Link to="/docs/releases/approval-policy-enforcement-0-24-20">0.24.20</Link>, fixed
          checks that some runtimes enforced and others skipped.
        </li>
        <li>
          <strong>The gap is still there in MCP.</strong> Side effects, approvals and recovery
          after a refusal are mostly free text that a client can show a model but cannot act on.
          That is the part of ANIP worth carrying over.
        </li>
      </ul>
    </section>
  );
}

function Next(): ReactNode {
  return (
    <section className={styles.section}>
      <Heading as="h2">What comes next</Heading>
      <ul>
        <li>
          <Link to={MAPPING}>ANIP as an MCP extension</Link>: how each ANIP concept maps onto MCP,
          what is dropped, and the open questions.
        </li>
        <li>
          <strong>
            <code>dev.anip/refusal</code>
          </strong>
          , planned: refusals that say what was refused, how to recover and who can grant it, with
          a reference implementation on the official MCP Python SDK.
        </li>
        <li>
          <strong>
            <code>dev.anip/approval-grants</code>
          </strong>
          , planned after that: approvals bound to the exact parameters they approve.
        </li>
        <li>
          Reversibility windows, cost and review reasons, offered to MCP&apos;s tool annotation
          drafts.
        </li>
      </ul>
    </section>
  );
}

function Frozen(): ReactNode {
  return (
    <section className={styles.section}>
      <Heading as="h2">ANIP protocol (frozen)</Heading>
      <p>
        The specification, the five runtimes, the CLI and the documentation stay available and
        receive security fixes only. The hosted Studio, Registry and Playground were shut down on
        26 November 2026.
      </p>
      <ul className={styles.linkList}>
        <li>
          <Link to="/docs/intro">ANIP documentation</Link>
        </li>
        <li>
          <Link to="/docs/releases/approval-policy-enforcement-0-24-20">
            Latest security release: 0.24.20
          </Link>
        </li>
        <li>
          <Link to="/docs/releases/version-history">Version history</Link>
        </li>
        <li>
          <Link to="https://github.com/anip-protocol/anip">Source on GitHub</Link>
        </li>
      </ul>
    </section>
  );
}

export default function Home(): ReactNode {
  return (
    <Layout
      title="ANIP's ideas are moving into MCP"
      description="ANIP is frozen to security fixes. Its ideas continue as MCP extensions and a conformance harness for MCP tool annotations.">
      <Hero />
      <main className="container">
        <Evidence />
        <WhyMove />
        <Next />
        <Frozen />
      </main>
    </Layout>
  );
}
