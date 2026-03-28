import type {ReactNode} from 'react';
import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

type FeatureItem = {
  title: string;
  eyebrow: string;
  description: ReactNode;
};

const FeatureList: FeatureItem[] = [
  {
    eyebrow: 'Before action',
    title: 'Agents see what will happen before they invoke',
    description: (
      <>
        Capability declarations carry side effects, rollback windows, cost
        expectations, prerequisites, and required authority up front.
      </>
    ),
  },
  {
    eyebrow: 'During action',
    title: 'Delegation, permissions, and failures are first-class',
    description: (
      <>
        ANIP tells an agent what it is allowed to do, why a call failed, who
        can grant missing authority, and how to recover.
      </>
    ),
  },
  {
    eyebrow: 'After action',
    title: 'Auditability and verification stay attached to execution',
    description: (
      <>
        Signed manifests, JWT delegation, audit logs, checkpoints, Studio, and
        testing tools make agent execution inspectable instead of opaque.
      </>
    ),
  },
];

function Feature({eyebrow, title, description}: FeatureItem) {
  return (
    <div className={clsx('col col--4')}>
      <div className={styles.card}>
        <div className={styles.eyebrow}>{eyebrow}</div>
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures(): ReactNode {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className={styles.intro}>
          <Heading as="h2">What ANIP adds</Heading>
          <p>
            ANIP is not just another transport or wrapper. It makes the
            execution boundary legible to agents.
          </p>
        </div>
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
        <div className={styles.matrix}>
          <div>
            <Heading as="h3">Core protocol surface</Heading>
            <ul>
              <li>Capability declaration</li>
              <li>Delegation and scoped JWT authority</li>
              <li>Permission discovery before invoke</li>
              <li>Structured failures and recovery hints</li>
              <li>Audit logs and checkpoints</li>
            </ul>
          </div>
          <div>
            <Heading as="h3">Shipping ecosystem</Heading>
            <ul>
              <li>HTTP, stdio, and gRPC bindings</li>
              <li>TypeScript, Python, Java, Go, and C# runtimes</li>
              <li>REST, GraphQL, and MCP adapters</li>
              <li>ANIP Studio for inspection and invocation</li>
              <li>Conformance and contract testing</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
