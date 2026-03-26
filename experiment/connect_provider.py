#!/usr/bin/env python3
"""
Simple provider connection manager inspired by `/connect` flows.

This script stores local auth profiles in a JSON file so other scripts can
reuse credentials without hardcoding keys in command invocations.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
from datetime import datetime
from getpass import getpass
from pathlib import Path
from typing import Any, Dict


DEFAULT_AUTH_FILE = Path(__file__).resolve().parent / "credentials.json"

PROVIDERS: Dict[str, Dict[str, str]] = {
    "openai": {
        "label": "OpenAI API",
        "provider": "openai-compatible",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-5.3-codex",
        "api_key_env": "OPENAI_API_KEY",
    },
    "zai": {
        "label": "Z.AI (OpenAI-compatible)",
        "provider": "openai-compatible",
        "base_url": "https://api.z.ai/api/coding/paas/v4",
        "model": "glm-4.6",
        "api_key_env": "ZAI_API_KEY",
    },
    "anthropic": {
        "label": "Anthropic API",
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com",
        "model": "claude-sonnet-4-5",
        "api_key_env": "ANTHROPIC_API_KEY",
    },
}


def mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def load_store(path: Path) -> dict:
    if not path.exists() or not path.is_file():
        return {"profiles": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"profiles": {}}
    if not isinstance(data, dict):
        return {"profiles": {}}
    if "profiles" not in data or not isinstance(data["profiles"], dict):
        data["profiles"] = {}
    return data


def write_store(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def choose_provider() -> str:
    options = list(PROVIDERS.keys())
    print("Select provider:")
    for idx, key in enumerate(options, start=1):
        print(f"  {idx}) {PROVIDERS[key]['label']}")
    while True:
        raw = input("Choice number: ").strip()
        try:
            index = int(raw)
        except ValueError:
            index = -1
        if 1 <= index <= len(options):
            return options[index - 1]
        print("Invalid choice. Please enter a valid number.")


def cmd_login(args: argparse.Namespace) -> int:
    auth_file = Path(args.auth_file).expanduser().resolve()
    provider_key = args.provider or choose_provider()
    if provider_key not in PROVIDERS:
        raise SystemExit(f"Unknown provider: {provider_key}")

    provider = PROVIDERS[provider_key]
    profile_name = args.profile or f"{provider_key}-default"

    print(f"Connecting: {provider['label']}")
    print("Auth method: API key")
    print(
        "Note: Browser OAuth using subscription sessions is not implemented here. "
        "Use official API keys for reliable automation."
    )

    env_var = provider["api_key_env"]
    default_key = os.getenv(env_var, "")
    if default_key:
        print(f"Found {env_var} in environment; press Enter to use it.")

    entered = getpass("API key: ").strip()
    api_key = entered or default_key
    if not api_key:
        raise SystemExit("Missing API key. Set one in env or enter it interactively.")

    model = (args.model or provider["model"]).strip()
    base_url = (args.base_url or provider["base_url"]).strip()

    store = load_store(auth_file)
    store["profiles"][profile_name] = {
        "provider": provider["provider"],
        "display_provider": provider_key,
        "auth": {
            "type": "api",
            "key": api_key,
        },
        "base_url": base_url,
        "model": model,
        "api_key_env": env_var,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    write_store(auth_file, store)

    print("Saved profile")
    print(f"- File: {auth_file}")
    print(f"- Profile: {profile_name}")
    print(f"- Provider: {provider_key} ({provider['provider']})")
    print(f"- Model: {model}")
    print(f"- Base URL: {base_url}")
    print(f"- Key: {mask_secret(api_key)}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    auth_file = Path(args.auth_file).expanduser().resolve()
    store = load_store(auth_file)
    profiles = store.get("profiles", {})
    if not profiles:
        print(f"No profiles found in {auth_file}")
        return 0

    print(f"Profiles in {auth_file}:")
    for name in sorted(profiles.keys()):
        p = profiles[name]
        key = p.get("auth", {}).get("key", "")
        print(
            f"- {name}: provider={p.get('provider')} model={p.get('model')} "
            f"base_url={p.get('base_url')} key={mask_secret(str(key))}"
        )
    return 0


def cmd_logout(args: argparse.Namespace) -> int:
    auth_file = Path(args.auth_file).expanduser().resolve()
    store = load_store(auth_file)
    profiles = store.get("profiles", {})
    if args.profile not in profiles:
        raise SystemExit(f"Profile not found: {args.profile}")
    del profiles[args.profile]
    write_store(auth_file, store)
    print(f"Removed profile {args.profile} from {auth_file}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Connect providers and store reusable auth profiles"
    )
    parser.add_argument(
        "--auth-file",
        default=str(DEFAULT_AUTH_FILE),
        help="Credentials JSON path (default: ./credentials.json)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="Create or update a profile")
    login.add_argument(
        "--provider",
        choices=sorted(PROVIDERS.keys()),
        default=None,
        help="Provider preset",
    )
    login.add_argument(
        "--profile",
        default=None,
        help="Profile name (default: <provider>-default)",
    )
    login.add_argument(
        "--model",
        default=None,
        help="Override default model for this profile",
    )
    login.add_argument(
        "--base-url",
        default=None,
        help="Override default base URL for this profile",
    )
    login.set_defaults(func=cmd_login)

    list_cmd = sub.add_parser("list", help="List saved profiles")
    list_cmd.set_defaults(func=cmd_list)

    logout = sub.add_parser("logout", help="Delete a saved profile")
    logout.add_argument("profile", help="Profile name")
    logout.set_defaults(func=cmd_logout)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
