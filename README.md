# LaC - LLM as Code

[![Release](https://img.shields.io/github/v/tag/diranix/llm-as-code?label=release)](https://github.com/diranix/llm-as-code/tags)
[![PyPI](https://img.shields.io/pypi/v/llm-as-code)](https://pypi.org/project/llm-as-code/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

> **Work in progress - not finished, not stable, and it holds plenty of bugs.**
> This is an active research build. The engine runs, but features are half-cured,
> the injection defense is an open front (see [Known limitations](#known-limitations)),
> and there are no tests or CI yet. APIs and the compose schema will change without
> notice. Read it, learn from it, break it - do not ship it.

LaC is a protocol for building LLM applications the way IaC builds infrastructure: behavior is declared in versioned artifacts, not improvised in prompts. An application is a folder of plain files - a compose declaration, law files with explicit authority levels, and a commands module. The engine is generic and knows nothing about any particular application.

This repository holds the LaC specification ([SPEC.md](SPEC.md)) and the reference engine. The engine is intentionally small: a compose loader with a strict parser, a context assembler that loads law in trust order (L1 then L2, with L3 kept out of the system channel), a REPL, and an agentic loop where free-form language and canonical `!commands` are two roads into the same code.

## Why LaC

The premise is a threat model, not a convenience: **an LLM application must protect the user's machine from its own model.** A model can be talked into anything - a note in a document, a line in a file, a stray instruction in retrieved data. So the guarantee cannot live in the model's good behavior; it has to live in structure and code the model does not control.

- **Behavior as code.** Prose asks; code enforces. Where a normal app improvises rules in a system prompt, LaC turns the load-bearing parts into deterministic mechanism - commands are modules, the write perimeter is a filesystem jail, consent is a real gate on stdin. Prose remains the law for the persona; it never guards the disk.
- **Capability, not promises.** A wrong action must be survivable. The engine's hands are caged (every path resolves through a realpath jail rooted at the memory folder); the model may misjudge, and the machine still stands.
- **Levels are authority.** L0 is code (the engine and command modules - executes, never enters the context). L1 is limits, L2 is behavior - both always in context. L3 is data - all stored content, with zero authority, never instructions. On any conflict the higher level wins, and nothing at L3 is promoted by being read, named, or retold.
- **A protocol, not one app.** The same law can run on more than one host. The Grimoire application runs this engine; its earlier form runs the same protocol on Claude Code with the perimeter enforced by harness permissions instead of engine code. One law, two hosts - that is the point.

A running theme of the work, and the reason for the honesty above: raising the model's system prompt was the wrong lever. Moving L3 data **out** of the system channel entirely - so the model receives law as law and data as data - did in one engine change what layers of defensive prose in an application could not. **Place in the structure is authority.** That result, and the ones still failing, are the substance; the numbers are being measured, not assumed.

## Core mechanics

- **Two roads, one code.** Canonical `!commands` bypass the model entirely (zero tokens); free-form requests reach the same functions through tool calling. The model interprets and narrates; code executes. A canonical command is fed back to the model as a real synthesized tool exchange, not pasted prose, so the model never re-issues what code already ran.
- **System prompt is L1/L2 only.** Boot data and all retrieved content arrive as conversation messages, never in the system channel. The system carries law; the conversation carries data.
- **A mark no file can wear.** Each run the engine draws half a mark at random and computes the other half from the law it actually loaded. Its own words carry that mark; stored content travels between borders that carry it, and imitations of the engine's framing are broken before the request is built. What is public can be copied - only what did not exist before the run resists forgery.
- **Perimeter in code.** Effects on disk are the engine's job: a write jail (realpath-rooted), a consent gate for destructive actions, and per-app write allowlists.
- **Retrieval-first.** Routing indexes stay in context; bulk content is fetched on demand and cited, not preloaded.

## Quick start

```
pipx install llm-as-code
cd your-app
lac
```

An application folder looks like:

```
your-app/
  .lac/
    llm_compose.yaml    # the anchor: all paths resolve relative to the app root
    law/                # L1/L2 law files
    souls/              # personas (L2)
    commands.py         # the app's command module (TOOLS + COMMANDS registry)
  <memory folders>      # L3 content
```

The engine finds `.lac/llm_compose.yaml` in the current directory (or in the directory passed as the first argument) and resolves every path in the compose against that root. No absolute paths anywhere.

Providers: Anthropic (raw HTTP, prompt + conversation caching, `ANTHROPIC_API_KEY` from env only), Mistral (`MISTRAL_API_KEY`), and Ollama for local models. The vendor surface lives in one dispatch table, `adapter.PROVIDERS`, behind `adapter.send()`; any OpenAI-shaped API is one new entry.

Trust model: the commands module is application code (L0) and the engine executes it deliberately - running an app means trusting its code, the same way installing any package means trusting its authors. The levels protect L1/L2 from the model and from L3 content, not the machine from the app you chose to run.

## Status and roadmap

Pre-release. The spec ([SPEC.md](SPEC.md), methodology v0.2) is the canon; this engine tracks it through milestones M0-M3 (loader, retrieval commands, write perimeter, drift metrics), with an M4 opening on refusing destructive user commands. The current focus is a debt pass - stabilize every existing feature before adding more.

These are limitations of **this engine and the protocol** - application-level defenses and their bugs (datamarking, memory hygiene, persona discipline) live with each application, e.g. the Grimoire.

- **Injection is not solved.** One class is now closed in code: text that forges the engine's own voice is broken before the model sees it, and the fixture that carried it was refused six runs out of six. Everything else stands open - a plain, plausible instruction sitting in a note imitates nothing, so nothing mechanical touches it, and there the defense is prose again. Measured through the day, on a mid-tier head: every defense that asked the model to *check* something failed on the first cold turn; only defenses that *removed* the attack held. The engine's guarantee remains that effects on disk are survivable, not that the model always obeys.
- **No tests or CI, no drift numbers yet.** The M3 harness (scripted turns, an LLM judge, deterministic checks, a model matrix) is designed but not built. Treat every claim here as a hypothesis under measurement.
- **Unstable surface.** APIs and the compose schema change without notice; SPEC.md still trails the engine on several points.
- **Behavioral hygiene varies by model.** Cheaper heads carry the mechanism but not the voice; stronger heads rationalize rather than obey. Perception is not a guarantee - which is the whole reason the perimeter is code.

## First application

[Grimoire](https://github.com/diranix/grimoire) - a conversational layer over the user's own markdown notes, and the first LaC application. It keeps no memory of its own: the engine lists, opens and greps the user's files, and what the model invents dies with the session. Its earlier implementation runs the same protocol on Claude Code, with the perimeter enforced by harness permissions instead of engine code: one law, two hosts.

## License

Apache-2.0. The protocol is free; applications built on it license themselves independently.
