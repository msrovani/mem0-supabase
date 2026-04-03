#!/usr/bin/env python3
"""
Mem0 CLI — Command-line interface for Mem0 Memory API.

Usage:
    mem0-cli add "User likes pizza" --user-id user1
    mem0-cli search "food preferences" --user-id user1
    mem0-cli get mem_123
    mem0-cli list --user-id user1 --limit 10
    mem0-cli delete mem_123
    mem0-cli health
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Optional

from mem0.client import Mem0Client


def get_client(args: argparse.Namespace) -> Mem0Client:
    """Create client from CLI args."""
    return Mem0Client(
        base_url=getattr(args, "base_url", "http://localhost:8000"),
        api_key=getattr(args, "api_key", None),
    )


def cmd_add(args: argparse.Namespace) -> int:
    """Add a memory."""
    client = get_client(args)
    result = client.add(
        args.message,
        user_id=args.user_id,
        agent_id=args.agent_id,
        run_id=args.run_id,
        idempotency_key=args.idempotency_key,
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Search memories."""
    client = get_client(args)
    result = client.search(
        args.query,
        user_id=args.user_id,
        agent_id=args.agent_id,
        run_id=args.run_id,
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    """Get a memory."""
    client = get_client(args)
    result = client.get(args.memory_id)
    print(json.dumps(result, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List memories."""
    client = get_client(args)
    result = client.get_all(
        user_id=args.user_id,
        agent_id=args.agent_id,
        run_id=args.run_id,
        cursor=args.cursor,
        limit=args.limit,
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """Delete a memory."""
    client = get_client(args)
    result = client.delete(args.memory_id)
    print(json.dumps(result, indent=2))
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    """Check health."""
    client = get_client(args)
    result = client.health()
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "healthy" else 1


def main():
    parser = argparse.ArgumentParser(
        prog="mem0-cli",
        description="Command-line interface for Mem0 Memory API",
    )
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--api-key", help="JWT authentication token")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # add
    add_parser = subparsers.add_parser("add", help="Add a memory")
    add_parser.add_argument("message", help="Memory content")
    add_parser.add_argument("--user-id")
    add_parser.add_argument("--agent-id")
    add_parser.add_argument("--run-id")
    add_parser.add_argument("--idempotency-key")
    add_parser.set_defaults(func=cmd_add)

    # search
    search_parser = subparsers.add_parser("search", help="Search memories")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--user-id")
    search_parser.add_argument("--agent-id")
    search_parser.add_argument("--run-id")
    search_parser.set_defaults(func=cmd_search)

    # get
    get_parser = subparsers.add_parser("get", help="Get a memory")
    get_parser.add_argument("memory_id", help="Memory ID")
    get_parser.set_defaults(func=cmd_get)

    # list
    list_parser = subparsers.add_parser("list", help="List memories")
    list_parser.add_argument("--user-id")
    list_parser.add_argument("--agent-id")
    list_parser.add_argument("--run-id")
    list_parser.add_argument("--cursor")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.set_defaults(func=cmd_list)

    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete a memory")
    delete_parser.add_argument("memory_id", help="Memory ID")
    delete_parser.set_defaults(func=cmd_delete)

    # health
    health_parser = subparsers.add_parser("health", help="Check API health")
    health_parser.set_defaults(func=cmd_health)

    args = parser.parse_args()

    try:
        sys.exit(args.func(args))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
