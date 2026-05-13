#!/usr/bin/env python3
"""Eco-Guard CLI — manage your self-hosted LLM inference gateway."""

import argparse
import json
import os
import sys
from pathlib import Path

SDK_PATH = Path(__file__).parent
sys.path.insert(0, str(SDK_PATH))

from __init__ import EcoGuard  # noqa: E402


def _get_client(args) -> EcoGuard:
    return EcoGuard(
        base_url=args.base_url or os.getenv("ECOGUARD_URL", "http://localhost:8000"),
        api_key=args.api_key or os.getenv("ECOGUARD_API_KEY"),
    )


def cmd_health(args):
    client = _get_client(args)
    result = client.health()
    print(json.dumps(result, indent=2))


def cmd_chat(args):
    client = _get_client(args)
    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": args.prompt})

    if args.stream:
        print("Streaming:\n")
        for chunk in client.chat_stream(
            messages, model=args.model, max_tokens=args.max_tokens
        ):
            choices = chunk.get("choices", [{}])
            delta = choices[0].get("delta", {})
            content = delta.get("content", "")
            if content:
                print(content, end="", flush=True)
        print()
    else:
        result = client.chat(messages, model=args.model, max_tokens=args.max_tokens)
        choices = result.get("choices", [{}])
        print(choices[0].get("message", {}).get("content", "No response"))


def cmd_predict(args):
    client = _get_client(args)
    result = client.predict(args.prompt, max_tokens=args.max_tokens)
    print(result.get("output", "No output"))


def cmd_models(args):
    client = _get_client(args)
    result = client.models()
    for model in result.get("data", []):
        print(f"  {model['id']} (owned_by={model['owned_by']})")


def cmd_cost(args):
    client = _get_client(args)
    result = client.cost_usage(hours=args.hours)
    print(f"Period: {result['period_hours']}h")
    print(f"Requests: {result['total_requests']}")
    print(f"Tokens: {result['total_input_tokens'] + result['total_output_tokens']}")
    print(f"Estimated cost: ${result['estimated_cost']:.4f}")


def cmd_estimate(args):
    client = _get_client(args)
    result = client.cost_estimate(
        input_tokens=args.input_tokens,
        output_tokens=args.output_tokens,
        model=args.model,
    )
    print(f"Model: {result['model']}")
    print(f"Input:  {result['input_tokens']} tokens → ${result['input_cost']}")
    print(f"Output: {result['output_tokens']} tokens → ${result['output_cost']}")
    print(f"Total:  ${result['total_cost']}")


def cmd_guardrails(args):
    client = _get_client(args)
    result = client.guardrails_check(args.prompt)
    for r in result.get("results", []):
        status = "✅" if r.get("action") == "allow" else "⚠️"
        print(
            f"  {status} {r.get('name')}: {r.get('action')} "
            f"({r.get('severity', '')}) — {r.get('message', '')}"
        )


def main():
    parser = argparse.ArgumentParser(description="Eco-Guard CLI")
    parser.add_argument("--base-url", help="Eco-Guard server URL")
    parser.add_argument("--api-key", help="API key or JWT token")

    sub = parser.add_subparsers(dest="command", required=True)

    p_health = sub.add_parser("health", help="Check server health")
    p_health.set_defaults(func=cmd_health)

    p_chat = sub.add_parser("chat", help="Chat completion")
    p_chat.add_argument("prompt", help="User prompt")
    p_chat.add_argument("--system", help="System prompt")
    p_chat.add_argument("--model", default="default", help="Model name")
    p_chat.add_argument("--max-tokens", type=int, default=512)
    p_chat.add_argument("--stream", action="store_true", help="Stream output")
    p_chat.set_defaults(func=cmd_chat)

    p_predict = sub.add_parser("predict", help="Legacy text completion")
    p_predict.add_argument("prompt", help="Prompt text")
    p_predict.add_argument("--max-tokens", type=int, default=128)
    p_predict.set_defaults(func=cmd_predict)

    p_models = sub.add_parser("models", help="List available models")
    p_models.set_defaults(func=cmd_models)

    p_cost = sub.add_parser("cost", help="View cost usage")
    p_cost.add_argument("--hours", type=int, default=24, help="Period in hours")
    p_cost.set_defaults(func=cmd_cost)

    p_estimate = sub.add_parser("estimate", help="Estimate cost")
    p_estimate.add_argument("--input-tokens", type=int, required=True)
    p_estimate.add_argument("--output-tokens", type=int, required=True)
    p_estimate.add_argument("--model", default="default")
    p_estimate.set_defaults(func=cmd_estimate)

    p_guard = sub.add_parser("guardrails", help="Check prompt against guardrails")
    p_guard.add_argument("prompt", help="Prompt to check")
    p_guard.set_defaults(func=cmd_guardrails)

    def cmd_backup(args):
        client = _get_client(args)
        import requests

        r = requests.post(f"{client.base_url}/api/v1/backup")
        print(json.dumps(r.json(), indent=2))

    def cmd_compare(args):
        client = _get_client(args)
        import requests

        r = requests.post(
            f"{client.base_url}/api/v1/cost/compare",
            json={"prompt": args.prompt, "max_tokens": args.max_tokens},
        )
        data = r.json()
        for p in data.get("providers", []):
            tag = " [self-hosted]" if p.get("self_hosted") else ""
            print(f"  {p['provider']}{tag}: ${p['total_cost']:.6f}")
        if data.get("cheapest"):
            print(f"\nCheapest: {data['cheapest']}")

    def cmd_digest(args):
        client = _get_client(args)
        import requests

        r = requests.get(f"{client.base_url}/api/v1/digest")
        print(json.dumps(r.json(), indent=2))

    p_backup = sub.add_parser("backup", help="Create a backup")
    p_backup.set_defaults(func=cmd_backup)

    p_compare = sub.add_parser("compare", help="Compare model costs")
    p_compare.add_argument("prompt", help="Prompt to estimate cost for")
    p_compare.add_argument("--max-tokens", type=int, default=128)
    p_compare.set_defaults(func=cmd_compare)

    p_digest = sub.add_parser("digest", help="View daily digest")
    p_digest.set_defaults(func=cmd_digest)

    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
