
% Paste these sections directly into your Overleaf template

\section{Introduction}
\noindent Modern software development depends on fast release cycles and highly automated delivery pipelines, but this speed also increases exposure to security defects. Traditional static analysis tools are widely used to detect vulnerabilities early, yet their outputs are often fragmented across tools and can include high false-positive rates that increase review effort. In parallel, Large Language Models (LLMs) are emerging as context-aware analyzers that may identify vulnerabilities beyond predefined rule patterns. This thesis investigates how these two approaches can be compared and combined in CI/CD workflows to improve practical vulnerability management.

\subsection{Background}
\noindent Modern software security in CI/CD builds on two major analysis paradigms: rule-based static analysis and AI-based code understanding.

Static Application Security Testing (SAST) refers to analyzing source code without executing it in order to identify potential vulnerabilities and insecure coding patterns [source needed here]. SAST tools typically rely on predefined rules, pattern matching, control-flow checks, and data-flow or taint analysis [source needed here]. In practice, these tools are widely used in shift-left security because they can run automatically during pull requests and build pipelines [source needed here].

Large Language Models (LLMs) introduce a different analysis paradigm. Instead of relying only on explicit handcrafted rules, LLMs use learned representations from large-scale code and text corpora to reason about code context and potential security issues [source needed here]. In software security tasks, this can improve contextual understanding and broad vulnerability coverage, but it can also introduce limitations such as false positives, hallucinated findings, and inconsistent localization accuracy [source needed here].

CI/CD security workflows are designed to integrate security checks continuously during development, testing, and deployment [source needed here]. The main goal is to detect defects early, reduce remediation cost, and provide actionable feedback to developers before release [source needed here]. However, real-world pipelines often involve multiple scanners with overlapping outputs, different severity scales, and heterogeneous report formats, which increases review effort and alert fatigue [source needed here].

To support interoperability between tools, result exchange standards such as SARIF (Static Analysis Results Interchange Format) are commonly used [source needed here]. SARIF provides a structured representation of findings, including rule identifiers, severity, messages, and code locations, making cross-tool comparison and aggregation easier in automated pipelines [source needed here]. This is relevant for this thesis because both static tools and LLM outputs need to be normalized into a shared machine-readable schema before comparative evaluation and orchestration.

Evaluation of vulnerability detection systems is commonly based on classification metrics. Precision measures how many reported findings are correct, recall measures how many real vulnerabilities are detected, and F1-score balances both [source needed here]. In security practice, false negatives are risky because real vulnerabilities remain undetected, while false positives increase manual triage cost and reduce trust in tooling [source needed here]. For CI/CD adoption, runtime and report usability are also important, since slow analysis and low-quality findings can disrupt developer workflows [source needed here].

Recent comparative studies report that LLM-based approaches can achieve strong recall and competitive overall detection effectiveness, while traditional static tools often remain more precise and stable in deterministic checks [source needed here]. These findings motivate hybrid designs where LLMs are used for broad contextual triage and static analyzers for stricter verification [source needed here].

\subsection{Problem Formulation}
\noindent This thesis investigates whether LLM-based security analysis can complement or outperform traditional static analysis in CI/CD workflows. The problem is formulated in two connected parts.

Part 1 focuses on detection performance. Given a codebase with known vulnerabilities, we run a set of traditional static analyzers and a set of LLM-based analyzers on the same input and normalize outputs into a shared JSON schema. We then compare the tools on common evaluation metrics such as precision, recall, and F1-score, and on practical metrics such as analysis time, false-positive burden, and quality of vulnerability localization.

Part 2 focuses on decision support. Given multiple vulnerability reports from both tool families, we evaluate whether an LLM orchestrator can aggregate duplicate findings, rank issues by remediation priority, and produce actionable guidance for developers in CI/CD. The central question is whether this orchestration layer improves remediation usefulness compared with reading raw tool outputs independently.

Formally, let $C$ be a set of software projects, $V$ be the ground-truth vulnerabilities for each project, $S$ be the set of static analyzers, and $L$ be the set of LLM-based analyzers. Each analyzer $a \in (S \cup L)$ produces a finding set $F_a(C_i)$ for project $C_i$. We evaluate each $F_a(C_i)$ against $V_i$ using standard classification metrics and compare aggregate performance across analyzers.

For aggregation, let $A(C_i)$ be the final report produced by the LLM orchestrator from all findings in $\{F_a(C_i)\}$. We assess $A(C_i)$ using criteria such as deduplication quality, prioritization relevance, clarity of remediation steps, and developer effort needed to act on the report.

This leads to two testable claims aligned with the research questions:
\begin{itemize}
  \item LLM-based analyzers achieve higher contextual coverage and recall than traditional static analyzers, with a trade-off in false positives and localization precision.
  \item An LLM orchestration layer over combined findings provides more actionable and prioritized remediation support than standalone tool reports.
\end{itemize}

The expected contribution is a reproducible benchmark setup and an evidence-based comparison that clarifies where static analysis, LLM analysis, and hybrid orchestration each provide the most value in CI/CD security practice.

\section{Related Work}
\subsection{Review of Existing Research}
\noindent Recent research has started to compare LLM-based vulnerability detection with traditional static analysis tools in controlled benchmark settings. A key study that is closely related to this thesis is the IEEE Access paper by Gnieciak and Szandala~\cite{gnieciak2025llm_vs_static}.

Gnieciak and Szandala~\cite{gnieciak2025llm_vs_static} conduct a systematic comparison between three static analyzers (SonarQube, CodeQL, SnykCode) and three LLMs (GPT-4.1, Mistral Large, DeepSeek V3). Their benchmark uses curated C\# projects with known vulnerabilities and evaluates performance using precision, recall, F1-score, runtime, and qualitative review effort. Their findings show that LLMs can achieve higher recall and stronger F1 results on average, while static tools often provide better precision and more stable localization. The authors recommend a hybrid workflow where LLMs are used for broad early triage and static analyzers are used for high-assurance verification.

\subsection{Identified Gaps and Positioning of This Work}
\noindent This thesis is aligned with that direction but extends the scope in two ways. First, it includes a broader CI/CD-oriented tool stack for detection, including SonarQube, Bandit, Bearer, CodeQL, and Fortify, alongside multiple LLMs. Second, it explicitly studies an LLM orchestration layer that aggregates findings from both families, deduplicates outputs, prioritizes remediation, and produces an actionable report. In this sense, our work moves from model-versus-tool comparison toward pipeline-level decision support in practical DevSecOps workflows.

The study by Gnieciak and Szandala~\cite{gnieciak2025llm_vs_static} therefore serves as both a methodological reference and a baseline expectation for trade-offs between recall, false positives, and localization quality. Our thesis builds on this foundation to evaluate whether hybrid orchestration improves operational usefulness for developer teams in CI/CD.

\subsection{BibTeX Source (.bib)}
\begin{verbatim}
@article{gnieciak2025llm_vs_static,
  author  = {Gnieciak, Damian and Szandala, Tomasz},
  title   = {Large Language Models Versus Static Code Analysis Tools: A Systematic Benchmark for Vulnerability Detection},
  journal = {IEEE Access},
  volume  = {13},
  pages   = {198410--198422},
  year    = {2025},
  doi     = {10.1109/ACCESS.2025.3635168}
}
\end{verbatim}
