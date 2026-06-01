---
status: verifying
trigger: "Debug: openai.BadRequestError: Thinking mode does not support this tool_choice when running examples/mix_query.py"
created: 2026-06-01T00:00:00Z
updated: 2026-06-01T00:00:00Z
---

## Current Focus

status: Fix applied and verified via code review. Awaiting human verification.
hypothesis: CONFIRMED — `method="function_calling"` in `llm.with_structured_output()` causes LangChain to set `tool_choice`, which DeepSeek v4-pro thinking mode rejects with 400.
fix_applied: Changed `method="function_calling"` to `method="json_mode"` in keywords.py (3 locations: docstring, function docstring, and actual call). `json_mode` uses `response_format={"type": "json_object"}` — no `tool_choice` involved.
next_action: Human to verify by running `python examples/mix_query.py` with DeepSeek v4-pro configured

## Symptoms

expected: `extract_keywords()` calls LLM with structured output and receives typed `KeywordsSchema` result
actual: `openai.BadRequestError: Error code: 400 - {'error': {'message': 'Thinking mode does not support this tool_choice', 'type': 'invalid_request_error'}}`
errors: "Thinking mode does not support this tool_choice"
reproduction: Run `python examples/mix_query.py` with DeepSeek v4-pro model configured in .env
started: Always broken with DeepSeek v4-pro (thinking mode is default or model-inherent)

## Eliminated

- hypothesis: Config issue — missing model_kwargs to disable thinking mode
  evidence: LlmConfig has no `model_kwargs` field, and `_LazyLLM` passes no extra params to ChatOpenAI. But this is a secondary concern — the immediate fix is on the client side.
  timestamp: 2026-06-01T00:00:00Z

## Evidence

- timestamp: 2026-06-01T00:00:00Z
  checked: src/lightrag_langchain/keywords.py lines 192-195
  found: `method="function_calling"` is passed to `llm.with_structured_output()`. This causes LangChain to set `tool_choice` in the API request body.
  implication: DeepSeek v4-pro thinking mode rejects requests with `tool_choice` set.

- timestamp: 2026-06-01T00:00:00Z
  checked: src/lightrag_langchain/llm.py `_LazyLLM.__getattr__`
  found: ChatOpenAI is constructed with only model, base_url, api_key, temperature, max_tokens. No `model_kwargs` or `extra_body` to enable/disable thinking mode.
  implication: Thinking mode comes from DeepSeek's API defaults for v4-pro model, not from client configuration.

- timestamp: 2026-06-01T00:00:00Z
  checked: src/lightrag_langchain/config.py LlmConfig model
  found: No `model_kwargs` field exists on LlmConfig. Only binding, binding_host, binding_api_key, model, temperature, max_tokens.
  implication: Users cannot disable thinking mode through configuration.

- timestamp: 2026-06-01T00:00:00Z
  checked: Entire codebase for `with_structured_output` usages
  found: Only `src/lightrag_langchain/keywords.py` uses `with_structured_output` (lines 192-195).
  implication: Fix is isolated to one file.

- timestamp: 2026-06-01T00:00:00Z
  checked: keywords.py prompt template (KEYWORDS_EXTRACTION_PROMPT)
  found: Prompt explicitly instructs: "你的输出必须是一个合法的 JSON 对象，除此之外不得有任何其他内容" (output must be a valid JSON object, nothing else).
  implication: The prompt already directs the model to output JSON, so `json_mode` (response_format) will work correctly.

## Resolution

root_cause: DeepSeek v4-pro thinking (reasoning) mode rejects API requests that include `tool_choice`. LangChain's `with_structured_output(method="function_calling")` causes OpenAI client to set `tool_choice` in the request, triggering a 400 error from DeepSeek.
fix: Change `method="function_calling"` to `method="json_mode"` in `keywords.py` line 194. `json_mode` uses `response_format={"type": "json_object"}` which is compatible with DeepSeek thinking mode. The keyword extraction prompt already instructs JSON output.
verification: Code review confirms fix is minimal and targeted. Cannot run example script (requires real database + API key), but the fix eliminates the only `tool_choice`-producing code path.
files_changed:
  - src/lightrag_langchain/keywords.py: change method parameter + update docstring
