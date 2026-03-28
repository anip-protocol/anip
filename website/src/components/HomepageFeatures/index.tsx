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
    eyebrow: 'What it is',
    title: 'ANIP describes how an agent should reason before it acts',
    description: (
      <>
        ANIP is a protocol for interfaces where authority, side effects,
        rollback posture, cost, and failure semantics are explicit parts of the
        contract.
      </>
    ),
  },
  {
    eyebrow: 'Why it exists',
    title: 'REST and MCP expose actions, but leave execution context implicit',
    description: (
      <>
        Agents still need to know what they are allowed to do, what will
        happen if they act, what it may cost, and how to recover if execution
        fails.
      </>
    ),
  },
  {
    eyebrow: 'What changes',
    title: 'ANIP makes permissions, recovery, and auditability part of the surface',
    description: (
      <>
        Services can declare side effects, expose permission discovery, return
        structured failures, and attach audit and checkpoint evidence to what
        ran.
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
          <Heading as="h2">Why ANIP is different</Heading>
          <p>
            ANIP is not just another transport or wrapper. It is a protocol for
            making agent execution legible, governable, and reviewable.
          </p>
        </div>
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
        <div className={styles.matrix}>
          <div>
            <Heading as="h3">What ANIP makes explicit</Heading>
            <ul>
              <li>Capability declarations and required authority</li>
              <li>Delegation and scoped JWT permissions</li>
              <li>Permission discovery before invoke</li>
              <li>Structured failures and recovery guidance</li>
              <li>Audit logs, checkpoints, and trust signals</li>
            </ul>
          </div>
          <div>
            <Heading as="h3">What teams can build with it</Heading>
            <ul>
              <li>Higher-trust internal agent workflows</li>
              <li>Operational and infrastructure actions with explicit rollback posture</li>
              <li>Services that expose native ANIP plus REST, GraphQL, and MCP adapters</li>
              <li>Multi-transport runtimes over HTTP, stdio, and gRPC</li>
              <li>Inspection and verification through Studio and testing tools</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
