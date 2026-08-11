# Changelog

## 0.3.0 - 2026-08-06

The session mark and the fence: the engine now signs its own words with a value no stored text can hold, and stored content travels inside borders only the engine can write. Breaking for apps that logged through the engine or relied on dot-paths being writable.

Breaking:

- The session journal is gone. No `.sessions` folder, no `env["log"]` - the engine writes nothing of its own. Apps that logged turns through it must drop those calls.
- `jail_write` no longer treats a dot-prefixed path as writable. Only paths listed in the app's `WRITABLE` set can be written; everything else under the memory root is read-only to the engine.
- Tool results carry no engine prose. The `[executed by code - relay it faithfully]` wrapper is gone: a result is the data and nothing else, and the engine's own note arrives after it as a separate message.
- `build_context` returns `(law, data_parts)` instead of `(law, data)`. L3 entries are labelled without their paths (a path reads as a page to open), and an empty L3 file is skipped instead of producing a header with no body.

New:

- **Session mark.** At boot the engine draws `uuid4().hex[:6]` and joins it to `sha256(law)[:6]`. Every word of the engine's own carries `[engine:MARK]`, and the appended law names it. Half of it cannot be known before the run, half changes with any edit to the law, so text written earlier cannot wear it.
- **`env["fence"]` and `env["scrub"]`.** Stored content arrives between `[engine:MARK:data]` and `[engine:MARK:end]` - borders a file cannot forge or close. Before fencing, the engine breaks anything inside that imitates its own framing (its mark in any shape, its banners, its level headers, the retired `l3-data` tags) and replaces it with `~forgery~`, counting the hits for the terminal. Applications declare their own framing in `EXTRA_FORGERIES`; each layer polices its own vocabulary, so the engine needs no knowledge of any app.
- **Boot material is fenced too.** The one payload loaded every session gets the same treatment as any tool result: each file's content is scrubbed, then labelled, then fenced.
- **`env["confirm"](question)`.** A consent gate an app can call from inside a command, for cases the tool-level `CONFIRM` set cannot express (a file over a size cap, for instance).
- **`env["messages"]`.** The live conversation window, so an application can drop content it loaded earlier instead of carrying it to the end of the session.
- **`VALIDATE` hook.** A map of command name to a check run before the consent gate: a call that will be refused anyway is refused without spending the user's yes.
- Adapter: the retry ladder is 5, 10, 20, 40 seconds over five attempts (a numeric `Retry-After` wins, capped at 60), and 5xx is retried like 429; the provider's resolved model name is announced once per session; Ollama calls now set `num_ctx` (16384) and `num_predict` explicitly - the default window was smaller than the law - and print their token usage.

Measured, not assumed: a fixture that forges the engine's own framing to plant a rule was obeyed by Mistral Medium 3.5 under every wording-only defense (tags, marks, borders alone), and refused six runs out of six once the imitation was broken in code before the request. The replacement text matters as much as the breaking - a residue that still reads as engine speech is evidence the model will believe.

## 0.2.0 - 2026-07-20

Breaking: both changes below require a one-line compose/file move in existing apps.

- `llm.persona` compose key: the persona file gets its own slot instead of hiding in the `context.L2` list. It loads as L2 right after the L2 files; a missing persona file refuses boot like any missing law. Optional - apps without personas declare nothing.
- The commands module moved into the machinery folder under a fixed name: the engine now loads `.lac/commands.py` instead of `commands_<app>.py` at the app root. The app root belongs to the user's content; `.lac/` holds everything the app runs on, and the module name is no longer derived from `app.name`. Update the compose `levels.L0` path, rename the module file, and re-run `lac lock`.

## 0.1.5 - 2026-07-14

Injection defense: the authority channel. Behavior unchanged for well-behaved input; the change is where data sits.

- L3 out of the system prompt: the system channel now carries L1/L2 law only. Boot data (core, map, tree) and all retrieved content arrive as the first conversation message, marked L3 - so the model receives law as law and data as data. `build_context` returns `(law, data)`; the adapter's `split_context` becomes `law_of`, and all three providers (Anthropic, Mistral, Ollama) build `system` from law alone. This closes the case where injection-shaped L3 text rode the same channel a model is trained to read as authority.
- Canonical commands feed back as a real tool exchange: instead of pasting the command result into a user message, the REPL synthesizes an `assistant` `tool_use` plus a `user` `tool_result` into the history (uuid tool-call id, 9 chars for Mistral). The model sees the result in the channel it expects, so it no longer re-issues a command code already executed (the double-load bug).
- Removed the L1 restatement mechanism (`build_context` no longer tracks `l1_parts`); the after-data law repetition is gone. Cancelled canonical commands now roll their user message back out of the history.

## 0.1.4 - 2026-07-13

- Distribution renamed: `lac-engine` -> `llm-as-code` (matches the paper's "LLM as Code"). The import package stays `lac`, the command stays `lac`. The GitHub repo moves to diranix/llm-as-code; `lac-engine` on PyPI is retired at 0.1.3.

## 0.1.3 - 2026-07-13

Second audit pass: protocol integrity and cost.

- fsjail canary at boot: the engine attempts a jail escape and refuses to start unless it is refused - the lock is verified, not assumed (SPEC 5.2).
- to_ollama_messages and to_mistral_messages folded into one to_openai_messages(with_ids) converter; ollama tool results now follow their assistant message.
- Anthropic conversation caching: cache_control rides the last message when tools are on, so the growing conversation is cached, not only the system prompt; `llm.cache_ttl: "1h"` switches to the extended-ttl beta.
- env["law_size"]: the engine hands apps its boot-context size estimate, so context policies can budget the conversation net of the always-present law.
- ON_TEXT hook now receives env - `ON_TEXT(env, text)` - so app text gates keep state without module globals.
- readline import is optional (the engine starts on Windows); 429 retry honors a numeric Retry-After header.

## 0.1.2 - 2026-07-13

Full audit of the engine: correctness, portability, and readability - behavior unchanged unless noted.

- Explicit utf-8 on every file the engine reads or writes (compose, context files, fsjail writes); behavior no longer depends on the OS default encoding.
- Compose loader: clean `compose error` messages for bad yaml, a non-mapping file, and missing required keys (app, paths, llm, context, context levels) instead of raw tracebacks.
- Unknown llm provider is refused at boot, for the head and the worker both; adapter's send() dispatches through a PROVIDERS table and raises ApiError instead of killing the session mid-turn.
- `llm.max_tokens` is a compose key (default 2048) instead of a hardcoded constant; applies to the anthropic and mistral providers.
- http_post survives a non-JSON response body: ApiError instead of an uncaught exception.
- Ctrl-C during a command no longer kills the REPL; the command returns "interrupted by the user" and the session continues.
- engine.py split into named phases (load_compose, load_commands, build_context, run_command, repl, main) - same flow, readable units.
- to_ollama_tools renamed to_openai_tools - mistral sends the same shape.

## 0.1.1 - 2026-07-09

Two boot-and-read hardenings, found by review and verified live.

- Boot refuses a broken law: a missing L1/L2 context file stops the engine (`law incomplete - refusing to start`); the MISSING list now names each file's level. Missing L3 stays a warning.
- Read jail in the commands contract: an app's load command must resolve paths with realpath and refuse anything outside the memory root (`../` escape closed). Applied in the Grimoire app (lives with the app, not in this package); read-side counterpart of the M2 write fsjail.

## 0.1.0 - 2026-07-09

First packaged release of the reference engine.

- Engine as an installable package: `pipx install lac-engine`, global `lac` command.
- App root anchor: the engine finds `.lac/llm_compose.yaml` in the current directory (or the directory given as an argument); all compose paths resolve relative to the app root. No absolute paths.
- Compose loader with a strict parser: schema_version gate, unknown-key rejection, clear errors for a missing compose or commands module.
- Context assembler: law loads in trust order L1 -> L2 -> L3, always in context.
- Commands module loaded per app by explicit file path (`commands_<app>.py`, TOOLS + COMMANDS registry).
- Two roads to the same code: canonical `!commands` intercepted before the model (zero tokens); free-form language through tool calling into the same functions.
- Providers behind `adapter.send()`: Anthropic (raw HTTP, prompt caching on system, usage line, API key from env only) and Ollama.
- Published on PyPI as `lac-engine`.
- SPEC.md: the LaC methodology (v0.2) - definition, philosophy, compose schema, levels, commands, security model, memory hierarchy.
- Adapter hardened: request timeout, readable api errors instead of tracebacks, soft recovery (an API failure prints one line and rolls the conversation back; the REPL survives).
- Ollama path reconciled with the agentic loop: messages and tools translate both ways; the loop no longer sees the provider.
- Known debt: drift metrics (M3) not started; no tests or CI yet.
