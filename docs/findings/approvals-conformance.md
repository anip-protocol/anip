# Approvals: what the first conformance tests found

Findings from adding `conformance/test_approvals.py` and running it against
the seven example services (branch `test/conformance-approvals`; link the pull
request here when it exists). Only the **Observed** part of each finding
carries a status.

### 1. A binding advertised an endpoint it did not serve

- **Observed:** Discovery is built by the service, not the binding. The Java
  Spring Boot binding had no `POST /anip/approval_grants` route (404) while
  its discovery document advertised one. The Quarkus binding had the route and
  its own tests; nothing ran the same requests against Spring Boot.
- **Status:** verified.
- **Recommendation:** When one runtime has several HTTP bindings, keep the
  endpoint contract in the service and run the same HTTP tests against each
  binding. A test that every advertised endpoint answers non-404 is cheap.
- **Applies to:** every runtime with more than one binding.

### 2. "Absent" and "empty" were told apart in three different ways

- **Observed:** For `"approval_grant": ""` Python and TypeScript answered
  `grant_not_found`, Go treated it as absent, and Java and C# skipped grant
  validation while still passing the value to the handler context. In Go the
  cause is a `string` field whose zero value means "absent"; gRPC (proto3
  `string`) still cannot tell the two apart.
- **Status:** verified.
- **Recommendation:** For every optional field that authorises something, test
  three inputs: absent, empty, whitespace. Decide what the handler may see
  before validation and test that too.
- **Applies to:** everything.

### 3. No runtime's unit tests ran an approved continuation to success

- **Observed:** Each runtime's approval tests stop at "the grant was reserved";
  the test handler still asks for approval on the continuation (the Python test
  says so in a comment). The first end-to-end run of request, grant and
  successful continuation was the conformance suite.
- **Status:** verified.
- **Recommendation:** Give test handlers the same shape as real ones (ask for
  approval only when no grant was reserved) and assert the handler's result.
- **Applies to:** everything.

### 4. An assertion joined by "or" hid an empty 400

- **Observed:** The Quarkus endpoint test for malformed JSON accepted "400 or
  415" and did not look at the body. The body was empty, not a failure object.
- **Status:** verified.
- **Recommendation:** Assert the failure `type`, and that `resolution` is
  present, on every refusal. See also finding 6 in
  [porting-to-a-new-sdk-version.md](porting-to-a-new-sdk-version.md).
- **Applies to:** everything.

### 5. Things that made a check look like something it was not

- **Observed:** `dotnet test --no-build` after a deliberate breakage had been
  restored still ran the broken binaries, and reported a failure that the
  source no longer had. **Status:** observed once.
- **Observed:** A streaming-path test against a capability that does not
  declare `streaming` fails with `streaming_not_supported` before it reaches
  the code under test (Go, Java). **Status:** verified.
- **Observed:** Restoring a deliberately broken file with `git checkout`
  discards any uncommitted fix in the same file. **Status:** verified (noticed
  before it happened).
- **Recommendation:** Rebuild after restoring; give streaming tests a
  streaming-capable capability; commit before breaking things on purpose.
- **Applies to:** C# for the first, everything for the others.

## Running the approval tests

- The suite needs a `$approval` entry in `--sample-inputs`
  (`conformance/samples/flight-service.json` has one) and skips with the reason
  when the service declares no `grant_policy`. **Status:** verified.
- The expired-request test only runs when the sample states
  `request_expires_within_seconds`; the examples' requests live 900 seconds, so
  it skips in CI. It passed on Python, TypeScript, Go, Java and C# with the
  policy temporarily set to 2 seconds. **Status:** verified.
