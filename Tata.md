MODE: AGENT / APPLY — FINAL INTEGRATION VALIDATION

The architectural refactoring is complete. Do not introduce another architecture or perform unnecessary refactoring.

Before declaring success, validate the actual application behavior.

Critical issue to investigate:
"execute()" still appears to bypass semantic routing unless "kind == "chat" and mode == "full"", defaulting to the documentary workflow otherwise.

Determine whether this causes previous tests to exercise the wrong execution path. Preserve legitimate evaluation and document-selection functionality, but ensure the semantic router is actually used for conversational requests.

Also verify:

1. Documentary requests without evidence must not silently fall back to general model knowledge.
2. Profile answers must be grounded in the actual MCP results. The documentary verifier may be inapplicable, but structured-data correctness must still be checked.
3. "user_profile" must retrieve only the necessary backend fields, not retrieve everything and filter afterward.
4. "resolve_and_execute_tools()" must use real tool schemas, authorized tool names and validated arguments returned by the model.
5. Mixed requests must correctly combine authorized user data with documentary evidence.
6. MLflow traces must preserve useful routing, tool and latency metrics without logging raw personal data.

Execute real integration tests through "ask()", covering identity, professional history, training, documents, mixed requests, general requests and unavailable sources.

Use synthetic data or approved sanitized fixtures.

For every test, record:

- Expected versus actual route.
- Expected versus executed MCP tools.
- Tool arguments and success/failure status.
- Whether the answer correctly uses the retrieved data.
- LLM/MCP calls, latency and token consumption when available.
- Explicit PASS/FAIL with failure reason.

A wrong route followed by a generic answer must be marked FAIL.

Fix confirmed defects only, then rerun the relevant tests.

Do not create additional frameworks, duplicate test suites or rewrite working RAG components.

Provide a concise final report with actual test results and remaining issues. Do not claim successful validation based only on syntax checks or static code inspection.
