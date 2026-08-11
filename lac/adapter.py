import json
import os
import time
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/chat"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
TIMEOUT = 240
DEFAULT_MAX_TOKENS = 2048
OLLAMA_CTX = 16384


class ApiError(Exception):
    pass


RETRY_CODES = {429, 500, 502, 503, 504}
RETRY_BASE = 5
RETRY_MAX = 60


def http_post(url, payload, headers, tries=5):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
    )
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                body = response.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code in RETRY_CODES and attempt < tries - 1:
                after = (e.headers.get("Retry-After") or "").strip()
                if after.isdigit():
                    wait = min(int(after), RETRY_MAX)
                else:
                    wait = min(RETRY_BASE * 2 ** attempt, RETRY_MAX)
                print(
                    "[HTTP", e.code, "- retrying in", wait,
                    "s, attempt", attempt + 2, "of", tries, "]",
                )
                time.sleep(wait)
                continue
            raise ApiError("HTTP " + str(e.code) + " - " + detail)
        except urllib.error.URLError as e:
            raise ApiError(str(e.reason))
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise ApiError(
                "bad response - not json: " + body.decode(errors="replace")[:300]
            )


SEEN_MODEL = None


def announce_model(name):
    """Name the head once - and again only if the provider swaps it."""
    global SEEN_MODEL
    if name and name != SEEN_MODEL:
        SEEN_MODEL = name
        print("[model]", name)


def law_of(context):
    if isinstance(context, str):
        return context
    return context["law"]


def to_openai_messages(messages, with_ids):
    out = []
    for message in messages:
        content = message["content"]
        if isinstance(content, str):
            out.append({"role": message["role"], "content": content})
            continue
        text = ""
        tool_calls = []
        tool_results = []
        for block in content:
            if block["type"] == "text":
                text += block["text"]
            elif block["type"] == "tool_use":
                if with_ids:
                    tool_calls.append(
                        {
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block["input"]),
                            },
                        }
                    )
                else:
                    tool_calls.append(
                        {
                            "function": {
                                "name": block["name"],
                                "arguments": block["input"],
                            }
                        }
                    )
            elif block["type"] == "tool_result":
                result = {"role": "tool", "content": block["content"]}
                if with_ids:
                    result["tool_call_id"] = block["tool_use_id"]
                tool_results.append(result)
        if tool_results:
            # Data first, the engine's own words after it - never merged.
            out.extend(tool_results)
            if text:
                out.append({"role": message["role"], "content": text})
        elif text or tool_calls:
            entry = {"role": message["role"], "content": text}
            if tool_calls:
                entry["tool_calls"] = tool_calls
            out.append(entry)
    return out


def to_openai_tools(tools):
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in tools
    ]


def send_ollama(context, messages, llm, tools):
    system = law_of(context)
    payload = {
        "model": llm["model"],
        "messages": [{"role": "system", "content": system}]
        + to_openai_messages(messages, with_ids=False),
        "stream": False,
        # Ollama's default window is smaller than the law - without this
        # the law is silently truncated and the run measures nothing.
        "options": {
            "num_ctx": OLLAMA_CTX,
            "num_predict": llm.get("max_tokens", DEFAULT_MAX_TOKENS),
        },
    }
    if tools:
        payload["tools"] = to_openai_tools(tools)
    answer = http_post(OLLAMA_URL, payload, {"Content-Type": "application/json"})
    if not llm.get("quiet"):
        announce_model(answer.get("model"))
        print(
            "[usage]",
            answer.get("prompt_eval_count", 0),
            "in /",
            answer.get("eval_count", 0),
            "out",
        )
    message = answer["message"]
    blocks = []
    if message.get("content"):
        blocks.append({"type": "text", "text": message["content"]})
    for index, call in enumerate(message.get("tool_calls") or []):
        blocks.append(
            {
                "type": "tool_use",
                "id": "ollama_" + str(index),
                "name": call["function"]["name"],
                "input": call["function"].get("arguments") or {},
            }
        )
    return {
        "role": "assistant",
        "content": blocks,
        "window": answer.get("prompt_eval_count", 0),
    }


def send_mistral(context, messages, llm, tools):
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise ApiError("MISTRAL_API_KEY is not set")
    system = law_of(context)
    payload = {
        "model": llm["model"],
        "max_tokens": llm.get("max_tokens", DEFAULT_MAX_TOKENS),
        "messages": [{"role": "system", "content": system}]
        + to_openai_messages(messages, with_ids=True),
    }
    if "temperature" in llm:
        payload["temperature"] = llm["temperature"]
    if tools:
        payload["tools"] = to_openai_tools(tools)
    answer = http_post(
        MISTRAL_URL,
        payload,
        {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
    )
    message = answer["choices"][0]["message"]
    blocks = []
    if message.get("content"):
        blocks.append({"type": "text", "text": message["content"]})
    for call in message.get("tool_calls") or []:
        arguments = call["function"].get("arguments") or {}
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        blocks.append(
            {
                "type": "tool_use",
                "id": call["id"],
                "name": call["function"]["name"],
                "input": arguments,
            }
        )
    usage = answer.get("usage") or {}
    if not llm.get("quiet"):
        announce_model(answer.get("model"))
        print(
            "[usage]",
            usage.get("prompt_tokens", 0),
            "in /",
            usage.get("completion_tokens", 0),
            "out",
        )
    return {
        "role": "assistant",
        "content": blocks,
        "window": usage.get("prompt_tokens", 0),
    }


def cache_last(messages, cache):
    last = dict(messages[-1])
    content = last["content"]
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    blocks = [dict(b) for b in content]
    blocks[-1]["cache_control"] = cache
    last["content"] = blocks
    return messages[:-1] + [last]


def send_anthropic(context, messages, llm, tools):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ApiError("ANTHROPIC_API_KEY is not set")
    cache = {"type": "ephemeral"}
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    if llm.get("cache_ttl") == "1h":
        cache["ttl"] = "1h"
        headers["anthropic-beta"] = "extended-cache-ttl-2025-04-11"
    system = [
        {
            "type": "text",
            "text": law_of(context),
            "cache_control": cache,
        }
    ]
    payload = {
        "model": llm["model"],
        "max_tokens": llm.get("max_tokens", DEFAULT_MAX_TOKENS),
        "system": system,
        "messages": cache_last(messages, cache) if tools else messages,
    }
    if "temperature" in llm:
        payload["temperature"] = llm["temperature"]
    if tools:
        payload["tools"] = tools
    answer = http_post(ANTHROPIC_URL, payload, headers)
    usage = answer["usage"]
    if not llm.get("quiet"):
        print(
            "[usage]",
            usage["input_tokens"],
            "in /",
            usage["output_tokens"],
            "out /",
            usage["cache_read_input_tokens"],
            "cached /",
            usage["cache_creation_input_tokens"],
            "written",
        )
    stop = answer.get("stop_reason")
    if stop not in ("end_turn", "tool_use"):
        print("[stop]", stop)
    return {
        "role": "assistant",
        "content": answer["content"],
        "window": usage["input_tokens"]
        + usage["cache_read_input_tokens"]
        + usage["cache_creation_input_tokens"],
    }


PROVIDERS = {
    "anthropic": send_anthropic,
    "mistral": send_mistral,
    "ollama": send_ollama,
}


def send(context, messages, llm, tools=None):
    provider = PROVIDERS.get(llm["provider"])
    if provider is None:
        raise ApiError("unknown llm provider: " + str(llm["provider"]))
    return provider(context, messages, llm, tools)
