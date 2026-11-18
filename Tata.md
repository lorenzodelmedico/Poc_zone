APPLY the proposed architectural correction plan. The architecture is approved.

Integrate these final requirements directly during implementation, without producing another planning iteration:

1. Never redirect an unavailable documentary capability to "general" as if the request were general knowledge. Return an explicit unavailable status.
2. Unified tool selection must support user-data and documentary capabilities, including mixed requests. Preserve the existing document search, reading, reranking, authorization and verification pipeline.
3. Execute MCP tools using their actual validated arguments. Parallelize only independent operations; preserve dependencies between document search and reading.
4. Ensure "user_profile" performs genuinely minimal retrieval at the backend level, rather than fetching a complete user context and filtering afterward. Never force this tool as a default when another tool is sufficient.
5. Preserve security and verification. Do not persist raw personal data in MLflow traces.
6. Reuse existing test files where possible. A test is successful only when the expected intent, tools, arguments and response are correct. No false PASS from generic fallbacks.

Keep existing components, remove obsolete special-case routing, and minimize unnecessary logic. Avoid new frameworks and unrelated changes.

Implement incrementally and run regression tests after each phase. Correct confirmed regressions before proceeding.

At completion, report only:

- Files and functions modified.
- Obsolete logic removed.
- Test results (PASS/FAIL).
- Remaining issues.
- Measured performance changes, if available.

Proceed with implementation now.
