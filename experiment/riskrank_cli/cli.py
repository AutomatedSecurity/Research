from __future__ import annotations

import argparse
import importlib
import sys
from typing import Sequence

from riskrank_cli import __version__


COMMANDS: dict[str, tuple[str, str]] = {
    "run": ("run_pipeline", "Run the full prioritization pipeline"),
    "fanin": ("fanin_rank", "Run fan-in ranking"),
    "git-history": ("git_history_rank", "Run git history ranking"),
    "vuln-scan": ("vulnerability_scan", "Run vulnerability signal scan"),
    "llm-scan": ("llm_reachability_scan", "Run LLM reachability scan"),
    "prioritize": ("prioritize_targets", "Build the prioritization table"),
    "report": ("generate_report", "Generate an HTML report from a run directory"),
    "connect": ("connect_provider", "Manage saved provider credentials"),
    "benchmark": (
        "evaluation.run_benchmark_suite",
        "Run the benchmark evaluation suite",
    ),
    "metrics": (
        "evaluation.compute_metrics",
        "Compute evaluation metrics from a benchmark suite",
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="riskrank",
        description="CLI for risk-based code prioritization",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")
    for command, (_, help_text) in COMMANDS.items():
        subparsers.add_parser(command, help=help_text, add_help=False)
    return parser


def run_module_main(module_name: str, argv: Sequence[str]) -> int:
    module = importlib.import_module(module_name)
    if not hasattr(module, "main"):
        raise SystemExit(f"Module does not expose main(): {module_name}")

    original_argv = sys.argv[:]
    try:
        sys.argv = [module_name, *argv]
        result = module.main()
    finally:
        sys.argv = original_argv

    return int(result) if isinstance(result, int) else 0


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    parsed, remainder = parser.parse_known_args(args_list)

    if not parsed.command:
        parser.print_help()
        return 1

    module_name = COMMANDS[parsed.command][0]
    return run_module_main(module_name, remainder)
