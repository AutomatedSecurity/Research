# Research

## Start Here

If you are new to the project, read these first:

1. `Research/md/OVERVIEW.md`
2. `Research/md/abstract.md`
3. `Research/md/2026-02-15.md`
4. `Research/experiment/README.md`

## RQ's
RQ1 - How can LLMs be leveraged to aggregate, analyze, and prioritize vulnerability findings from multiple security tools within a CI/CD context?



# Master Thesis Context

## Title
AI-Driven Security Solutions in Software Development: Comparing Traditional Static Analysis with LLM-Based Approaches for Vulnerability Detection in CI/CD Pipelines

## Overview
This thesis focuses on how LLMs can aggregate, analyze, and prioritize vulnerability findings from multiple static analysis tools into actionable remediation plans within CI/CD workflows.

## Architecture
Detection and prioritization architecture:

1. **Traditional static detection**: Bearer, SonarQube, Fortify, Bandit, CodeQL (and potentially more). Each outputs results as JSON.
2. **LLM-based prioritization layer**: LLMs process combined tool outputs and project context to produce structured, prioritized remediation guidance.

All outputs feed into an **LLM orchestrator** that aggregates, deduplicates, prioritizes, and synthesizes findings into a unified **Report** delivered within the CI/CD pipeline.

## Research Questions

- **RQ1:** How can LLMs be leveraged to aggregate, analyze, and prioritize vulnerability findings from multiple security tools within a CI/CD context?

## Thesis Progression
RQ1 (LLM as aggregator/planner in CI/CD)

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
