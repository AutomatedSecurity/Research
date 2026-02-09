# Research

## RQ's
RQ1 - How does LLM-based vulnerability detection compare to traditional static analysis tools in terms of accuracy, coverage, and contextual understanding?

RQ2 - How can LLMs be leveraged to aggregate, analyze, and prioritize vulnerability findings from multiple security tools within a CI/CD context?



# Master Thesis Context

## Title
AI-Driven Security Solutions in Software Development: Comparing Traditional Static Analysis with LLM-Based Approaches for Vulnerability Detection in CI/CD Pipelines

## Overview
This thesis evaluates and compares traditional static analysis tools with LLM-based approaches for vulnerability detection, then explores how LLMs can aggregate and prioritize combined findings into actionable remediation plans within CI/CD workflows.

## Architecture
Two parallel detection paths:

1. **Traditional static detection**: Bearer, SonarQube, Fortify, Bandit, CodeQL (and potentially more). Each outputs results as JSON.
2. **LLM-based detection**: Multiple LLMs (Claude, GPT, GLM, Kimi) analyze the same codebase using a shared JSON schema to produce structured vulnerability reports as JSON.

These two paths are compared against each other (RQ1 and RQ2).

Both sets of JSON outputs then feed into an **LLM orchestrator** that aggregates, prioritizes, and synthesizes all findings into a unified **Report** delivered within the CI/CD pipeline (RQ3).

## Research Questions

- **RQ1:** How does LLM-based vulnerability detection compare to traditional static analysis tools in terms of accuracy, coverage, and contextual understanding?
- **RQ2:** How can LLMs be leveraged to aggregate, analyze, and prioritize vulnerability findings from multiple security tools within a CI/CD context?

## Thesis Progression
RQ1 (LLM vs traditional detection comparison) → RQ2 (LLM as aggregator/planner in CI/CD)

## Key Tools and Technologies
- **Static analysis tools**: SonarQube, Bandit, Bearer, CodeQL, Fortify
- **LLMs for detection**: Claude, GPT, GLM, Kimi
- **Output format**: JSON (shared schema for LLMs)
- **Integration target**: CI/CD pipelines
- **LLM orchestrator**: aggregates all outputs into a final prioritized report

## Writing Style Preferences
- No em dashes
- Keep language simple and clear
- Avoid unnecessary complexity in phrasing
- Output all references/sources in LaTeX `.bib` format
- Write draft sections in Overleaf/LaTeX-ready format for direct copy-paste
