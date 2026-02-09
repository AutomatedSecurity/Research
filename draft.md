
## Current Introduction Draft
In modern software development, security vulnerabilities pose significant risks to software products and organizational infrastructure. Traditional static analysis tools have long served as the foundation for automated vulnerability detection, yet they often produce fragmented results, high false-positive rates, and lack contextual prioritization, contributing to alert fatigue among development teams. More recently, Large Language Models (LLMs) offer enhanced capabilities by learning from patterns, contextualizing findings, and potentially identifying vulnerabilities that rule-based tools may miss.

Integrating security analysis into CI/CD pipelines enables shift-left security practices, where vulnerabilities are detected and remediated early in the development lifecycle, reducing costs and improving overall security posture. However, questions remain about how LLM-based approaches compare to established static analysis tools in detection capability, and whether LLMs can effectively serve as an aggregation layer that synthesizes outputs from multiple tools into coherent and prioritized remediation plans.

The objective of this master thesis is twofold. First, it aims to evaluate and compare both traditional static analysis tools (SonarQube, Bandit, Bearer, CodeQL, Fortify) and LLM-based approaches for vulnerability detection within CI/CD environments. Second, it explores how LLMs can be used to aggregate, analyze, and prioritize the combined results from these tools, producing actionable security insights that support efficient remediation workflows.


## Problem Formulation Draft
This thesis investigates whether LLM-based security analysis can complement or outperform traditional static analysis in CI/CD workflows. The problem is formulated in two connected parts.

Part 1 focuses on detection performance. Given a codebase with known vulnerabilities, we run a set of traditional static analyzers and a set of LLM-based analyzers on the same input and normalize outputs into a shared JSON schema. We then compare the tools on common evaluation metrics such as precision, recall, and F1-score, and on practical metrics such as analysis time, false-positive burden, and quality of vulnerability localization.

Part 2 focuses on decision support. Given multiple vulnerability reports from both tool families, we evaluate whether an LLM orchestrator can aggregate duplicate findings, rank issues by remediation priority, and produce actionable guidance for developers in CI/CD. The central question is whether this orchestration layer improves remediation usefulness compared with reading raw tool outputs independently.

Formally, let C be a set of software projects, V be the ground-truth vulnerabilities for each project, S be the set of static analyzers, and L be the set of LLM-based analyzers. Each analyzer a in (S union L) produces a finding set F_a(C_i) for project C_i. We evaluate each F_a(C_i) against V_i using standard classification metrics and compare aggregate performance across analyzers.

For aggregation, let A(C_i) be the final report produced by the LLM orchestrator from all findings in {F_a(C_i)}. We assess A(C_i) using criteria such as deduplication quality, prioritization relevance, clarity of remediation steps, and developer effort needed to act on the report.

This leads to two testable claims aligned with the research questions:

1. LLM-based analyzers achieve higher contextual coverage and recall than traditional static analyzers, with a trade-off in false positives and localization precision.
2. An LLM orchestration layer over combined findings provides more actionable and prioritized remediation support than standalone tool reports.

The expected contribution is a reproducible benchmark setup and an evidence-based comparison that clarifies where static analysis, LLM analysis, and hybrid orchestration each provide the most value in CI/CD security practice.

