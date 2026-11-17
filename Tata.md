MODE: PLAN — ARCHITECTURAL CORRECTION

The current implementation has accumulated excessive hardcoded routing, special cases, legacy branches and regressions.

Stop patching individual queries. The objective is to restore a simple, generic, MCP-driven RAG application.

Target architecture

The application must have three clear responsibilities:

1. Semantic routing: understand the user request and identify the required capability domain (user data, documents, mixed, general or clarification when necessary).
2. MCP tool selection and execution: discover available authorized tools from real MCP metadata, select only the necessary tools, validate their arguments and execute them.
3. Answer generation and verification: generate a response strictly from relevant retrieved data, with appropriate authorization, provenance and verification.

Preserve the existing semantic router, FastMCP integration, backend connectors, document retrieval, verification and MLflow infrastructure.

Do not introduce LangGraph, a new planner, or additional framework abstractions.

Required corrections

1. Eliminate query-specific routing logic

Remove hardcoded keyword checks such as "is_who_am_i" and other special cases based on user phrasing.

Do not replace them with new regexes or keyword lists.

The examples "Qui suis-je ?", "Mon parcours professionnel" and "Mes formations" must be handled through the normal semantic routing and MCP tool-selection mechanisms.

2. Correct routing responsibilities

Inspect "route_question()", "choose_workflow()", "execute()" and "ask()".

The current "choose_workflow()" can overwrite the profile intent whenever document search is enabled. Correct this architectural defect.

Document availability must constrain accessible capabilities, not force every request into document search.

Remove "kind" and "mode" conditions from business-intent routing. Preserve any genuinely necessary evaluation and document-selection behavior at the appropriate execution boundary.

Keep clarification as an uncertainty or missing-information outcome, not as an additional business workflow.

3. Unify dynamic tool selection

The current dynamic selection is restricted to the profile branch. The overall application must support tools for user data, document retrieval and requests requiring both.

Use explicit capability groups and actual MCP schemas, not duplicated hardcoded tool descriptions.

Do not force "user_profile", "user_jobs" and "user_training_requests" for generic identity questions.

Preserve the tool-call name, arguments and identifier. Validate each selection against the authorized registry and execute using the actual validated arguments, never automatically "{}".

Do not automatically call "user_profile" when selection returns no usable tools. Diagnose the selection failure and handle it explicitly.

4. Restore minimal user-data retrieval

The "user_profile" operation must expose a minimal response by default: first name, last name, current position and site, when available and authorized.

Detailed employment history and training data must only be retrieved when relevant to the question.

Use field projection or a suitable MCP output contract, not a full-context retrieval followed by arbitrary truncation.

Remove fixed prompts imposing a comprehensive profile summary regardless of the request. Answer from the data actually requested and returned.

5. Preserve the complete RAG application

Do not damage the existing "search_documents", "read_documents", document authorization, reranking, citations or verification pipeline.

Inspect the "mixed" workflow carefully: the initial "context" is now empty because eager "get_context()" was removed. Mixed requests must retrieve relevant user data dynamically rather than silently losing the profile component.

Keep the "general" workflow for genuinely general requests, but never use a generic response to hide a failed profile or document retrieval.

6. Remove duplicated and obsolete logic

Audit "app/agent.py" and its related routing modules for obsolete logic, duplicate workflow selection, unused flags, dead branches and contradictory prompts.

Favor a small orchestration layer with clear functions and a single source of routing decisions.

Do not rewrite existing working components or remove input validation, access controls or audit mechanisms solely to reduce lines of code.

Ensure that profile outputs and model prompts are not inadvertently persisted as raw personal data in MLflow traces.

Validation requirements

First establish the expected route and tools for representative scenarios:

- Basic identity: user profile with minimal fields.
- Professional history: jobs only.
- Training requests: training data only.
- Documentary question: authorized documentary retrieval.
- Mixed profile/document request: both relevant sources.
- Ambiguous request: clarification.
- General question: no unnecessary profile or document calls.

Test the entire flow from "ask()" through semantic routing, MCP tool selection, execution, response generation and verification.

Every test must assert expected route, actual tools, arguments, data relevance, answer status and errors. A generic fallback answering the wrong intent is a FAIL.

Measure LLM/MCP calls, payload sizes and latency in MLflow.

Expected delivery

Do not modify code yet.

First provide:

1. A concise, evidence-based inventory of problematic, obsolete and necessary logic in the current files.
2. A minimal target architecture using existing components.
3. Exact functions to keep, simplify, remove or modify.
4. An incremental implementation sequence with regression tests.

Use the existing project conventions and files. No unnecessary new modules, test files or additional infrastructure.

The goal is less custom logic, fewer unnecessary calls and a fully functional application — not another collection of special-case fixes.

Stop after the plan and await approval before APPLY.
