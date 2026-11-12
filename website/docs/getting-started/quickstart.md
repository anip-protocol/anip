---
title: Quickstart
description: Run an ANIP service in about ten minutes, then issue a token, invoke a capability, see a refusal and read the audit log.
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import Snippet from '@site/src/components/Snippet';

import pyApp from '!!raw-loader!@site/snippets/quickstart/python/app.py';
import pyRequirements from '!!raw-loader!@site/snippets/quickstart/python/requirements.txt';
import tsApp from '!!raw-loader!@site/snippets/quickstart/typescript/app.ts';
import tsPackage from '!!raw-loader!@site/snippets/quickstart/typescript/package.json';
import goMain from '!!raw-loader!@site/snippets/quickstart/go/main.go';
import goMod from '!!raw-loader!@site/snippets/quickstart/go/go.mod';
import javaApp from '!!raw-loader!@site/snippets/quickstart/java/src/main/java/quickstart/Application.java';
import javaPom from '!!raw-loader!@site/snippets/quickstart/java/pom.xml';
import csProgram from '!!raw-loader!@site/snippets/quickstart/csharp/Program.cs';
import csProject from '!!raw-loader!@site/snippets/quickstart/csharp/Quickstart.csproj';
import walkthrough from '!!raw-loader!@site/snippets/quickstart/walkthrough.sh';

# Quickstart

In about ten minutes you will have a service with two capabilities, and you will have:

1. read what the service offers, before authenticating;
2. issued a token that is good for one capability;
3. invoked that capability;
4. been refused for the other one, with a reason and the name of who can fix it;
5. read both calls back from a signed audit log.

Every file and command on this page is run in CI against the published packages. If something here fails for you, that is a bug: please [open an issue](https://github.com/anip-protocol/anip/issues).

## 1. Create the service

The service declares two capabilities. `search_flights` only reads. `book_flight` cannot be undone, and needs a different scope.

Pick a language. The steps after this one are the same for all of them.

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

**You need:** Python 3.11 or newer.

Create a folder with these two files.

<Snippet src={pyRequirements} language="text" title="requirements.txt" />

<Snippet src={pyApp} language="python" title="app.py" />

Install and run:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --port 9100
```

</TabItem>
<TabItem value="typescript" label="TypeScript">

**You need:** Node.js 20 or newer.

Create a folder with these two files.

<Snippet src={tsPackage} language="json" title="package.json" />

<Snippet src={tsApp} language="typescript" title="app.ts" />

Install and run:

```bash
npm install
npm start
```

</TabItem>
<TabItem value="go" label="Go">

**You need:** Go 1.25 or newer.

Create a folder with these two files.

<Snippet src={goMod} language="go" title="go.mod" />

<Snippet src={goMain} language="go" title="main.go" />

Install and run:

```bash
go mod tidy
go run .
```

</TabItem>
<TabItem value="java" label="Java">

**You need:** Java 17 or newer, and Maven.

Create a folder with these two files.

<Snippet src={javaPom} language="xml" title="pom.xml" />

<Snippet src={javaApp} language="java" title="src/main/java/quickstart/Application.java" />

Run:

```bash
mvn spring-boot:run
```

</TabItem>
<TabItem value="csharp" label="C#">

**You need:** the .NET 10 SDK.

Create a folder with these two files.

<Snippet src={csProject} language="xml" title="Quickstart.csproj" />

<Snippet src={csProgram} language="csharp" title="Program.cs" />

Run:

```bash
dotnet run
```

</TabItem>
</Tabs>

The service is now listening on `http://localhost:9100`. Leave it running and open a second terminal.

## 2. Walk through the protocol

The commands below need `curl` and `python3` (used only to pull the token out of a JSON reply). To run them all at once, download [`walkthrough.sh`](https://github.com/anip-protocol/anip/blob/main/website/snippets/quickstart/walkthrough.sh).

```bash
BASE=http://localhost:9100
```

### Read what the service offers

No credentials are needed for this.

<Snippet src={walkthrough} language="bash" region="discovery" />

The reply lists each capability with its side effect and the scope it needs. Shortened:

```json
{
  "anip_discovery": {
    "protocol": "anip/0.24",
    "capabilities": {
      "search_flights": {
        "description": "Search available flights between two airports",
        "side_effect": "read",
        "minimum_scope": ["travel.search"]
      },
      "book_flight": {
        "description": "Book a flight",
        "side_effect": "irreversible",
        "minimum_scope": ["travel.book"]
      }
    },
    "trust_level": "signed",
    "endpoints": {
      "manifest": "/anip/manifest",
      "tokens": "/anip/tokens",
      "permissions": "/anip/permissions",
      "invoke": "/anip/invoke/{capability}",
      "audit": "/anip/audit"
    }
  }
}
```

An agent can tell from this, before doing anything, that booking cannot be undone.

### Issue a token

`demo-key` stands for however you already authenticate people: an API key, a session, single sign-on. The service's `authenticate` function maps it to a principal, here `human:demo@example.com`.

That person now hands an agent a token that is good for searching and nothing else.

<Snippet src={walkthrough} language="bash" region="token" />

The token names the agent it was given to, the one capability it may invoke, and its scope. By default it expires after two hours.

### Ask what the token allows

<Snippet src={walkthrough} language="bash" region="permissions" />

```json
{
  "available": [
    { "capability": "search_flights", "scope_match": "travel.search" }
  ],
  "restricted": [
    {
      "capability": "book_flight",
      "reason": "delegation chain lacks scope(s): travel.book",
      "grantable_by": "human:demo@example.com",
      "resolution_hint": "request_broader_scope"
    }
  ],
  "denied": []
}
```

The agent learns what it may do by asking, not by trying and failing.

### Invoke a capability

<Snippet src={walkthrough} language="bash" region="invoke" />

```json
{
  "success": true,
  "result": {
    "flights": [
      { "flight_number": "AA100", "origin": "SEA", "destination": "SFO", "price": 420 },
      { "flight_number": "DL310", "origin": "SEA", "destination": "SFO", "price": 280 }
    ]
  },
  "invocation_id": "inv-7d9d64c38bcd",
  "task_id": "task-anip-8e2b9bc71f09"
}
```

### See a refusal

Now try to book with the same token.

<Snippet src={walkthrough} language="bash" region="refusal" />

```json
{
  "success": false,
  "failure": {
    "type": "scope_insufficient",
    "detail": "delegation chain lacks scope(s): travel.book",
    "resolution": {
      "action": "request_broader_scope",
      "recovery_class": "redelegation_then_retry",
      "requires": "delegation.scope += travel.book",
      "grantable_by": "human:demo@example.com"
    }
  },
  "invocation_id": "inv-e426ae4a5e3e"
}
```

The booking code never ran. The agent is told what is missing and who can grant it, so it can go and ask instead of guessing.

### Read the audit log

<Snippet src={walkthrough} language="bash" region="audit" />

Both calls are there, the refused one included. Each entry carries the token it was made with, the person at the root of that token's chain, the hash of the entry before it, and a signature. Shortened:

```json
{
  "entries": [
    {
      "capability": "book_flight",
      "success": false,
      "failure_type": "scope_insufficient",
      "token_id": "anip-8e2b9bc71f09",
      "root_principal": "human:demo@example.com",
      "delegation_chain": ["anip-8e2b9bc71f09"],
      "event_class": "high_risk_denial",
      "sequence_number": 2,
      "previous_hash": "sha256:b916110f8438...",
      "signature": "eyJhbGciOiJFUzI1NiIs..."
    },
    {
      "capability": "search_flights",
      "success": true,
      "token_id": "anip-8e2b9bc71f09",
      "root_principal": "human:demo@example.com",
      "delegation_chain": ["anip-8e2b9bc71f09"],
      "event_class": "low_risk_success",
      "sequence_number": 1,
      "previous_hash": "sha256:0",
      "signature": "eyJhbGciOiJFUzI1NiIs..."
    }
  ]
}
```

## What you have now

Compared with the same two functions behind a plain REST endpoint or an MCP tool:

- **Declared side effects.** A caller can see that `book_flight` is irreversible before calling it.
- **Tokens for one purpose.** The agent held a token for searching. It could not book with it, and it could not have widened it.
- **Refusals that say what to do.** Not a bare 403: the missing scope, and who can grant it.
- **An audit log you did not write.** Every call, allowed or refused, linked to the person who delegated the authority.

The quickstart does not show approvals, spending budgets, delegation to a sub-agent, or exposing the same service over MCP. Those are next.

## Next steps

- **[Delegation and permissions](/docs/protocol/delegation-permissions)**: hand a narrower token to a sub-agent, and put a budget on a scope.
- **[Capability declaration](/docs/protocol/capabilities)**: cost, approval and the other things a capability can declare.
- **[Interfaces](/docs/generated-services/interfaces)**: expose the same service over MCP, REST or GraphQL.
- **[ANIP and MCP](/docs/concepts/anip-vs-mcp)**: how the two fit together.
- **[Install](/docs/getting-started/install)**: the full package list for each language.
