MODE: AGENT / APPLY — FIX VALIDATION BLOCKER

The integration report incorrectly declares SUCCESS despite only 2 out of 6 scenarios passing.

Do not modify the architecture or add new functionality.

1. Fix the Unicode encoding failure

Investigate the exact origin of the "UnicodeEncodeError: 'charmap' codec can't encode character '\\u202f'".

Identify whether the exception comes from LLM debug printing, subprocess output, logging, or another component.

Apply a minimal, robust UTF-8 fix at the relevant I/O boundary, compatible with the existing Windows environment.

Preserve Unicode content in model responses. Do not modify or strip model-generated text to hide encoding problems.

2. Correct validation reporting

- A test interrupted by an exception is ERROR, never PASS.
- Print the failure stage, exception class and sanitized traceback.
- Report actual tool calls, route, response status and execution time.
- Distinguish PASS, FAIL and ERROR.
- Never report overall SUCCESS unless every required scenario passes.
- Do not treat successful syntax checks as functional validation.

3. Rerun the six existing end-to-end scenarios

Validate:

- Identity
- Professional history
- Training
- Document retrieval
- Mixed user-data/document retrieval
- General conversation

For each scenario, verify the actual route, selected and executed tools, validated arguments, retrieved data, final answer and verification status.

The test must FAIL if the answer falls back to general knowledge instead of answering a request that requires retrieved data.

4. Preserve the current implementation

Do not introduce new frameworks, files, redundant fallback mechanisms or special-case routing.

Reuse existing tests and logging infrastructure.

Fix only confirmed defects, rerun the affected scenarios, then execute the complete suite.

Expected report

Provide the final PASS/FAIL/ERROR results, the root cause of any remaining failures, actual latency and LLM/MCP calls.

Do not declare completion while tests remain failed or unexecuted.
