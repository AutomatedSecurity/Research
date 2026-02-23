
% Paste these sections directly into your Overleaf template

\section{Introduction}
\noindent Modern software development depends on fast release cycles and highly automated delivery pipelines, but this speed also increases exposure to security defects. Traditional static analysis tools are widely used to detect vulnerabilities early, yet their outputs are often fragmented across tools and can include high false-positive rates that increase review effort. Large Language Models (LLMs) are emerging as context-aware reasoning components that can aggregate heterogeneous findings and improve prioritization quality. This thesis investigates how LLMs can be used as an orchestration and prioritization layer over multi-tool security findings in CI/CD workflows.

\subsection{Background}
\noindent Modern software security in CI/CD builds on two major analysis paradigms: rule-based static analysis and AI-based code understanding.

Static Application Security Testing (SAST) refers to analyzing source code without executing it in order to identify potential vulnerabilities and insecure coding patterns [source needed here]. SAST tools typically rely on predefined rules, pattern matching, control-flow checks, and data-flow or taint analysis [source needed here]. In practice, these tools are widely used in shift-left security because they can run automatically during pull requests and build pipelines [source needed here].

Large Language Models (LLMs) introduce a different analysis paradigm. Instead of relying only on explicit handcrafted rules, LLMs use learned representations from large-scale code and text corpora to reason about code context and potential security issues [source needed here]. In software security tasks, this can improve contextual understanding and broad vulnerability coverage, but it can also introduce limitations such as false positives, hallucinated findings, and inconsistent localization accuracy [source needed here].

CI/CD security workflows are designed to integrate security checks continuously during development, testing, and deployment [source needed here]. The main goal is to detect defects early, reduce remediation cost, and provide actionable feedback to developers before release [source needed here]. However, real-world pipelines often involve multiple scanners with overlapping outputs, different severity scales, and heterogeneous report formats, which increases review effort and alert fatigue [source needed here].

To support interoperability between tools, result exchange standards such as SARIF (Static Analysis Results Interchange Format) are commonly used [source needed here]. SARIF provides a structured representation of findings, including rule identifiers, severity, messages, and code locations, making cross-tool comparison and aggregation easier in automated pipelines [source needed here]. This is relevant for this thesis because both static tools and LLM outputs need to be normalized into a shared machine-readable schema before comparative evaluation and orchestration.

Evaluation of vulnerability detection systems is commonly based on classification metrics. Precision measures how many reported findings are correct, recall measures how many real vulnerabilities are detected, and F1-score balances both [source needed here]. In security practice, false negatives are risky because real vulnerabilities remain undetected, while false positives increase manual triage cost and reduce trust in tooling [source needed here]. For CI/CD adoption, runtime and report usability are also important, since slow analysis and low-quality findings can disrupt developer workflows [source needed here].

Recent comparative studies report that LLM-based approaches can achieve strong recall and competitive overall detection effectiveness, while traditional static tools often remain more precise and stable in deterministic checks [source needed here]. These findings motivate hybrid designs where LLMs are used for broad contextual triage and static analyzers for stricter verification [source needed here].

\subsection{Problem Formulation}
\noindent This thesis investigates how an LLM orchestration layer can improve security triage quality in CI/CD by aggregating and prioritizing outputs from multiple static analysis tools. Given a codebase scanned by several tools, findings are normalized into a shared JSON schema and enriched with contextual signals such as static reachability and repository change history.

The central question is whether this orchestration layer can deduplicate overlapping alerts, rank issues by practical remediation priority, and provide more actionable guidance than raw scanner outputs.

This leads to the following testable claim aligned with the research question:
\begin{itemize}
  \item An LLM orchestration layer over combined findings provides more actionable and prioritized remediation support than standalone tool reports.
\end{itemize}

The expected contribution is a reproducible prioritization pipeline and evidence-based analysis of how LLM-guided aggregation improves practical triage in CI/CD security workflows.

\subsection{Motivation}
\noindent This problem is worth investigating because secure software delivery now depends on fast and continuous development workflows, where delayed or low-quality vulnerability feedback can directly increase security risk.

From a \textbf{scientific research} perspective, this thesis contributes to the ongoing discussion on LLM-assisted security triage in realistic CI/CD settings. It evaluates an orchestration layer that combines outputs from multiple tools instead of treating each tool in isolation.

From an \textbf{industry} perspective, practitioners need evidence on how to reduce alert fatigue and improve remediation focus when multiple scanners are used together. The findings can support better pipeline design and more actionable security triage for development teams.

From a \textbf{societal} perspective, improving early vulnerability detection helps reduce the likelihood of security incidents that affect users, organizations, and public digital services. More reliable and actionable CI/CD security practices can therefore contribute to safer software systems at scale.

\subsection{Objectives}
\noindent The project objectives are defined to be specific, measurable, and directly linked to the research problem.

\begin{tabular}{|p{1.2cm}|p{11.6cm}|}
\hline
\textbf{O1} & Design a reproducible pipeline that runs multiple static analyzers on the same code projects using a shared output schema. \\
\hline
\textbf{O2} & Implement static contextual signals (for example reachability fan-in and git history frequency/churn) for vulnerability prioritization. \\
\hline
\textbf{O3} & Implement LLM-based semantic prioritization that consumes code context and multi-tool findings in a structured JSON format. \\
\hline
\textbf{O4} & Implement an LLM orchestration layer that aggregates outputs from multiple tools, deduplicates findings, and produces prioritized remediation guidance. \\
\hline
\textbf{O5} & Evaluate whether the orchestrated report improves actionability for developers compared with reading standalone tool reports. \\
\hline
\end{tabular}

\noindent These objectives are assessed as completed when each corresponding artifact is produced and evaluated:
\begin{itemize}
  \item O1 is completed when the benchmark pipeline and shared schema are implemented and executable.
  \item O2 is completed when contextual prioritization signals are generated and exported as structured artifacts.
  \item O3 is completed when LLM prioritization outputs are generated in the required schema for orchestration.
  \item O4 is completed when the orchestration component generates unified, prioritized reports.
  \item O5 is completed when a structured comparison of report actionability is performed and documented.
\end{itemize}

\section{Related Work}
\subsection{Review of Existing Research}
\noindent Recent research has started to compare LLM-based vulnerability detection with traditional static analysis tools in controlled benchmark settings. A key study that is closely related to this thesis is the IEEE Access paper by Gnieciak and Szandala~\cite{gnieciak2025llm_vs_static}.

Gnieciak and Szandala~\cite{gnieciak2025llm_vs_static} conduct a systematic comparison between three static analyzers (SonarQube, CodeQL, SnykCode) and three LLMs (GPT-4.1, Mistral Large, DeepSeek V3). Their benchmark uses curated C\# projects with known vulnerabilities and evaluates performance using precision, recall, F1-score, runtime, and qualitative review effort. Their findings show that LLMs can achieve higher recall and stronger F1 results on average, while static tools often provide better precision and more stable localization. The authors recommend a hybrid workflow where LLMs are used for broad early triage and static analyzers are used for high-assurance verification.

\subsection{Identified Gaps and Positioning of This Work}
\noindent This thesis is aligned with that direction but shifts focus to CI/CD prioritization and decision support. It includes a CI/CD-oriented tool stack for detection, including SonarQube, Bandit, Bearer, CodeQL, and Fortify, and explicitly studies an LLM orchestration layer that aggregates findings, deduplicates outputs, prioritizes remediation, and produces an actionable report.

The study by Gnieciak and Szandala~\cite{gnieciak2025llm_vs_static} therefore serves as a methodological reference. Our thesis builds on this foundation to evaluate whether LLM orchestration improves operational usefulness for developer teams in CI/CD.

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
