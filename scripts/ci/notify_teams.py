#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a test summary to a Microsoft Teams webhook.")
    parser.add_argument("--webhook-url", default="", help="Microsoft Teams webhook URL.")
    parser.add_argument("--status", required=True, help="PASSED or FAILED.")
    parser.add_argument("--environment", default="unknown", help="Test environment name.")
    parser.add_argument("--repo", default="", help="Repository name.")
    parser.add_argument("--branch", default="", help="Branch or ref name.")
    parser.add_argument("--duration-minutes", default="unknown", help="Test duration in minutes.")
    parser.add_argument("--total", default="unknown", help="Total tests.")
    parser.add_argument("--passed", default="unknown", help="Passed tests.")
    parser.add_argument("--failed", default="unknown", help="Failed tests.")
    parser.add_argument("--skipped", default="unknown", help="Skipped tests.")
    parser.add_argument("--run-url", default="", help="Workflow run URL.")
    parser.add_argument("--title", default="HL7 Unit Test Results", help="Message title.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.webhook_url:
        print("TEAMS_WEBHOOK_URL not set; skipping notification.")
        return 0

    theme_color = "2EB886" if args.status.upper() == "PASSED" else "A30200"
    facts = [
        {"name": "Environment", "value": args.environment},
        {"name": "Repo", "value": args.repo},
        {"name": "Branch", "value": args.branch},
        {"name": "Duration (min)", "value": args.duration_minutes},
        {"name": "Total Tests", "value": args.total},
        {"name": "Passed", "value": args.passed},
        {"name": "Failed", "value": args.failed},
        {"name": "Skipped", "value": args.skipped},
        {"name": "Run", "value": args.run_url},
    ]

    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "summary": args.title,
        "themeColor": theme_color,
        "title": f"{args.title} ({args.status.upper()})",
        "sections": [{"facts": facts}],
    }

    request = urllib.request.Request(
        args.webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            print(f"Teams notification sent: HTTP {response.status}")
    except urllib.error.URLError as exc:
        print(f"Failed to send Teams notification: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
