import { join } from 'node:path'
import { createError, getRouterParam } from 'h3'
import { fileExists, resolveRunDir, safeReadJson, summarizeManifest } from '../../utils/runs'

type BaselineTarget = {
  path?: string
  before_rank?: number
  before_score?: number
  findings?: number
  max_cvss?: number
  high_findings?: number
  medium_findings?: number
  low_findings?: number
}

type PriorityTarget = {
  rank?: number
  path?: string
  priority_score?: number
  priority_tier?: string
  llm_score?: number
  llm_rank?: number
  llm_confidence?: string
  max_cvss?: number
  vuln_findings?: number
  why?: string
  fan_in?: number
  fanin_rank?: number
  git_commits_touched?: number
  git_churn?: number
  git_rank?: number
  max_cvss_vector?: string
  avg_cvss?: number
  high_findings?: number
  primary_vuln_line?: number
  primary_vuln_rule?: string
  primary_vuln_category?: string
  primary_vuln_severity?: string
  primary_vuln_cvss?: number
  primary_vuln_snippet?: string
  vuln_evidence?: Array<Record<string, unknown>>
}

export default defineEventHandler(async (event) => {
  const runId = getRouterParam(event, 'runId') ?? ''
  const runDir = resolveRunDir(runId)
  if (!runDir) {
    throw createError({ statusCode: 400, statusMessage: 'Invalid run id' })
  }

  const manifestPath = join(runDir, 'manifest.json')
  if (!(await fileExists(manifestPath))) {
    throw createError({ statusCode: 404, statusMessage: 'Run not found' })
  }

  const manifest = await safeReadJson<Record<string, unknown>>(manifestPath)
  const baseline = await safeReadJson<{ ranked_files?: BaselineTarget[] }>(
    join(runDir, 'vulnerabilities', 'baseline_ranking.json'),
  )
  const prioritization = await safeReadJson<{ top_priorities?: PriorityTarget[] }>(
    join(runDir, 'prioritization', 'summary.json'),
  )

  const plain = (baseline?.ranked_files ?? []).map((item) => ({
    path: item.path ?? '',
    targetType: 'file',
    symbol: null,
    rank: item.before_rank ?? null,
    score: item.before_score ?? null,
    confidence: null,
    why: `codeql findings=${item.findings ?? 0}, max_cvss=${item.max_cvss ?? 0}`,
    meta: {
      findings: item.findings ?? 0,
      maxCvss: item.max_cvss ?? 0,
      highFindings: item.high_findings ?? 0,
      mediumFindings: item.medium_findings ?? 0,
      lowFindings: item.low_findings ?? 0,
    },
  }))

  const prioritized = (prioritization?.top_priorities ?? []).map((item) => ({
    path: item.path ?? '',
    rank: item.rank ?? null,
    priorityScore: item.priority_score ?? null,
    priorityTier: item.priority_tier ?? null,
    llmScore: item.llm_score ?? null,
    llmRank: item.llm_rank ?? null,
    llmConfidence: item.llm_confidence ?? null,
    maxCvss: item.max_cvss ?? null,
    vulnFindings: item.vuln_findings ?? null,
    why: item.why ?? '',
    meta: {
      fanIn: item.fan_in ?? null,
      faninRank: item.fanin_rank ?? null,
      gitCommitsTouched: item.git_commits_touched ?? null,
      gitChurn: item.git_churn ?? null,
      gitRank: item.git_rank ?? null,
      maxCvssVector: item.max_cvss_vector ?? '',
      avgCvss: item.avg_cvss ?? null,
      highFindings: item.high_findings ?? null,
      primaryVulnLine: item.primary_vuln_line ?? null,
      primaryVulnRule: item.primary_vuln_rule ?? '',
      primaryVulnCategory: item.primary_vuln_category ?? '',
      primaryVulnSeverity: item.primary_vuln_severity ?? '',
      primaryVulnCvss: item.primary_vuln_cvss ?? null,
      primaryVulnSnippet: item.primary_vuln_snippet ?? '',
      vulnEvidence: item.vuln_evidence ?? [],
    },
  }))

  const plainByPath = new Map(plain.map((row) => [row.path, row]))
  const prioritizedByPath = new Map(prioritized.map((row) => [row.path, row]))
  const paths = new Set<string>([...plainByPath.keys(), ...prioritizedByPath.keys()])

  const comparison = [...paths]
    .filter((path) => path.length > 0)
    .sort((a, b) => a.localeCompare(b))
    .map((path) => {
      const before = plainByPath.get(path) ?? null
      const after = prioritizedByPath.get(path) ?? null
      return {
        path,
        before,
        after,
        rankChange:
          before?.rank && after?.rank && before.rank > 0 && after.rank > 0
            ? before.rank - after.rank
            : null,
      }
    })

  return {
    runId,
    manifest: summarizeManifest(manifest as Record<string, unknown>),
    counts: {
      plain: plain.length,
      prioritized: prioritized.length,
      compared: comparison.length,
    },
    plain,
    prioritized,
    comparison,
    files: {
      baselineRanking: join(runDir, 'vulnerabilities', 'baseline_ranking.json'),
      prioritizationSummary: join(runDir, 'prioritization', 'summary.json'),
      prioritizationCsv: join(runDir, 'prioritization', 'priorities.csv'),
    },
  }
})
