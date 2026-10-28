"""Explicit, single-attempt API transport. No hidden retries or model substitution."""
from __future__ import annotations
import os
import httpx
from .common import AuditError, require, strict_loads

class ProviderFailure(AuditError):
    def __init__(self, code, status=None, raw=None):
        super().__init__(code)
        self.code = code
        self.http_status = status
        self.raw = raw

def parse_response(raw):
    if not isinstance(raw, dict):
        raise ProviderFailure("invalid_response_schema", raw=raw)
    choices = raw.get("choices", [])
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise ProviderFailure("unexpected_choice_count", raw=raw)
    c = choices[0]; message = c.get("message", {})
    if not isinstance(message, dict):
        raise ProviderFailure("invalid_message_schema", raw=raw)
    if message.get("refusal"):
        raise ProviderFailure("model_refusal", raw=raw)
    if c.get("finish_reason") != "stop":
        raise ProviderFailure("incomplete_or_filtered_output", raw=raw)
    try:
        result = strict_loads(message["content"])
    except (AuditError, KeyError, TypeError):
        raise ProviderFailure("invalid_output_json", raw=raw)
    if not isinstance(result, dict) or set(result) != {"caption"} or not isinstance(result["caption"], str) or not result["caption"].strip() or len(result["caption"]) > 2500:
        raise ProviderFailure("invalid_caption_schema", raw=raw)
    usage = raw.get("usage") or {}
    if not isinstance(usage, dict):
        raise ProviderFailure("invalid_usage_schema", raw=raw)
    return {"caption": result["caption"].strip(), "response_id": raw.get("id"),
            "returned_model": raw.get("model"), "system_fingerprint": raw.get("system_fingerprint"),
            "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
            "usage": usage, "raw_response": raw}

class OpenAIProvider:
    def __init__(self, model_config, client=None):
        self.config = model_config
        key = os.environ.get(model_config["api_key_env"], "")
        require(bool(key.strip()), f"Set {model_config['api_key_env']} in your local PowerShell session. Never put it in a config file.")
        self.key = key
        self.owns_client = client is None
        self.client = client or httpx.Client(timeout=model_config["timeout_seconds"], follow_redirects=False)

    def close(self):
        if self.owns_client:
            self.client.close()

    def generate(self, body, client_request_id):
        require(body["model"] == self.config["model"], "Request model differs from frozen configuration")
        try:
            r = self.client.post(self.config["base_url"] + "/chat/completions", json=body,
                headers={"Authorization": "Bearer " + self.key, "X-Client-Request-Id": client_request_id})
        except httpx.TimeoutException as exc:
            raise ProviderFailure("timeout_billing_outcome_unknown") from exc
        except httpx.HTTPError as exc:
            raise ProviderFailure("network_error_billing_outcome_unknown") from exc
        if r.status_code != 200:
            # Provider error bodies may echo a partial API key; never persist them.
            raise ProviderFailure("http_error", status=r.status_code)
        try:
            raw = r.json()
        except ValueError as exc:
            raise ProviderFailure("non_json_http_response") from exc
        result = parse_response(raw)
        if result["returned_model"] != body["model"]:
            raise ProviderFailure("unexpected_returned_model", raw=raw)
        result["http_request_id"] = r.headers.get("x-request-id")
        return result

