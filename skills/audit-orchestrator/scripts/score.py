#!/usr/bin/env python3
"""
score.py — Computes ai_readiness_score and summary counts from deduplicated findings.

Formula (deterministic):
    score = max(0, 100 - critical*25 - high*10 - medium*4 - low*1)

Usage (called by build_report.py):
    from score import compute_summary
    summary = compute_summary(findings)
"""

import json
import sys


def compute_summary(findings: list[dict]) -> dict:
    """
    Compute the summary block from a list of deduplicated findings.

    Args:
        findings: list of normalized, deduplicated Finding dicts

    Returns:
        summary dict with total_findings, severity counts,
        ai_readiness_score, and by_category counts.
    """
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    by_category = {"discoverability": 0, "engagement": 0}

    for f in findings:
        sev = f.get("severity", "low")
        if sev in counts:
            counts[sev] += 1

        cat = f.get("category", "discoverability")
        if cat in by_category:
            by_category[cat] += 1

    score = max(
        0,
        100
        - counts["critical"] * 25
        - counts["high"] * 10
        - counts["medium"] * 4
        - counts["low"] * 1
    )

    return {
        "total_findings": len(findings),
        "critical": counts["critical"],
        "high": counts["high"],
        "medium": counts["medium"],
        "low": counts["low"],
        "ai_readiness_score": score,
        "by_category": by_category
    }


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Path to deduplicated_findings.json")
    p.add_argument("--output", default="summary.json")
    args = p.parse_args()

    try:
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)
        findings = data.get("findings", data) if isinstance(data, dict) else data
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    summary = compute_summary(findings)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"[OK] Score: {summary['ai_readiness_score']}/100 "
          f"(C:{summary['critical']} H:{summary['high']} "
          f"M:{summary['medium']} L:{summary['low']}) → {args.output}",
          file=sys.stderr)
