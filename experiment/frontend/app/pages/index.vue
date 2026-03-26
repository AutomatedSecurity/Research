<script setup lang="ts">
type RunListItem = {
  runId: string
  project: string | null
  prUrl: string | null
  prFilesCount: number | null
  steps: {
    fanin: boolean
    git_history: boolean
    vulnerabilities: boolean
    llm: boolean
    prioritization: boolean
  }
}

type RunListResponse = {
  runsDir: string
  count: number
  runs: RunListItem[]
}

type ComparisonRow = {
  path: string
  before: {
    rank: number | null
    score: number | null
    confidence: string | null
    why: string
    meta?: {
      findings?: number
      maxCvss?: number
      highFindings?: number
      mediumFindings?: number
      lowFindings?: number
    }
  } | null
  after: {
    rank: number | null
    priorityScore: number | null
    priorityTier: string | null
    maxCvss: number | null
    vulnFindings: number | null
    why: string
    llmScore?: number | null
    llmRank?: number | null
    llmConfidence?: string | null
    meta?: {
      fanIn?: number | null
      faninRank?: number | null
      gitCommitsTouched?: number | null
      gitChurn?: number | null
      gitRank?: number | null
      maxCvssVector?: string
      avgCvss?: number | null
      highFindings?: number | null
      primaryVulnLine?: number | null
      primaryVulnRule?: string
      primaryVulnCategory?: string
      primaryVulnSeverity?: string
      primaryVulnCvss?: number | null
      primaryVulnSnippet?: string
      vulnEvidence?: Array<Record<string, unknown>>
    }
  } | null
  rankChange: number | null
}

type RunDetailResponse = {
  runId: string
  counts: {
    plain: number
    prioritized: number
    compared: number
  }
  files: {
    baselineRanking: string
    prioritizationSummary: string
    prioritizationCsv: string
  }
  comparison: ComparisonRow[]
}

const selectedRunId = ref('')

const { data: runsData, status: runsStatus, error: runsError } = await useFetch<RunListResponse>('/api/runs')

watchEffect(() => {
  if (!selectedRunId.value && runsData.value?.runs?.length) {
    selectedRunId.value = runsData.value.runs[0].runId
  }
})

const details = ref<RunDetailResponse | null>(null)
const detailsStatus = ref<'idle' | 'pending' | 'success' | 'error'>('idle')
const detailsError = ref<string | null>(null)

watch(
  selectedRunId,
  async (runId) => {
    if (!runId) {
      details.value = null
      return
    }
    detailsStatus.value = 'pending'
    detailsError.value = null
    try {
      details.value = await $fetch<RunDetailResponse>(`/api/runs/${encodeURIComponent(runId)}`)
      detailsStatus.value = 'success'
    } catch (error) {
      details.value = null
      detailsStatus.value = 'error'
      detailsError.value = error instanceof Error ? error.message : 'Failed to load run details'
    }
  },
  { immediate: true },
)

const runOptions = computed(() => runsData.value?.runs ?? [])
const onlyVuln = ref(false)
const sortMode = ref<'after' | 'before' | 'largestChange' | 'vuln'>('after')
const expandedPaths = ref<Set<string>>(new Set())

const visibleRows = computed(() => {
  const rows = details.value?.comparison ?? []
  const filtered = onlyVuln.value
    ? rows.filter((row) => (row.after?.vulnFindings ?? 0) > 0)
    : rows

  return [...filtered].sort((a, b) => {
    if (sortMode.value === 'before') {
      return normalizeRank(a.before?.rank).localeCompare(normalizeRank(b.before?.rank), undefined, { numeric: true })
    }

    if (sortMode.value === 'largestChange') {
      return (Math.abs(b.rankChange ?? 0) - Math.abs(a.rankChange ?? 0)) || a.path.localeCompare(b.path)
    }

    if (sortMode.value === 'vuln') {
      return (
        (b.after?.vulnFindings ?? 0) - (a.after?.vulnFindings ?? 0) ||
        (b.after?.maxCvss ?? 0) - (a.after?.maxCvss ?? 0) ||
        a.path.localeCompare(b.path)
      )
    }

    return normalizeRank(a.after?.rank).localeCompare(normalizeRank(b.after?.rank), undefined, { numeric: true })
  })
})

const movedUpCount = computed(() => visibleRows.value.filter((row) => (row.rankChange ?? 0) > 0).length)
const movedDownCount = computed(() => visibleRows.value.filter((row) => (row.rankChange ?? 0) < 0).length)
const unchangedCount = computed(() => visibleRows.value.filter((row) => (row.rankChange ?? 0) === 0).length)

function normalizeRank(rank: number | null | undefined): string {
  if (!rank || rank <= 0) {
    return '999999'
  }
  return String(rank).padStart(6, '0')
}

function formatRankChange(value: number | null): string {
  if (value === null) {
    return '-'
  }
  if (value > 0) {
    return `+${value}`
  }
  return `${value}`
}

function rankTrend(value: number | null): 'up' | 'down' | 'same' | 'na' {
  if (value === null) {
    return 'na'
  }
  if (value > 0) {
    return 'up'
  }
  if (value < 0) {
    return 'down'
  }
  return 'same'
}

function cvssClass(cvss: number | null | undefined): string {
  const value = cvss ?? 0
  if (value >= 9) return 'cvss-critical'
  if (value >= 7) return 'cvss-high'
  if (value >= 4) return 'cvss-medium'
  if (value > 0) return 'cvss-low'
  return 'cvss-none'
}

function toggleExpanded(path: string): void {
  const next = new Set(expandedPaths.value)
  if (next.has(path)) {
    next.delete(path)
  } else {
    next.add(path)
  }
  expandedPaths.value = next
}

function isExpanded(path: string): boolean {
  return expandedPaths.value.has(path)
}
</script>

<template>
  <main class="page">
    <section class="panel hero">
      <h1>Vulnerability Prioritization Diff</h1>
      <p class="subtitle">Compare CodeQL vulnerability baseline ordering against the post-prioritization order in a cleaner, risk-focused view.</p>

      <div v-if="runsStatus === 'pending'">Loading runs...</div>
      <div v-else-if="runsError">Failed to load runs: {{ runsError.message }}</div>
      <template v-else class="controls">
        <label for="run-select">Run</label>
        <select id="run-select" v-model="selectedRunId">
          <option v-for="run in runOptions" :key="run.runId" :value="run.runId">
            {{ run.runId }}
          </option>
        </select>

        <p v-if="runOptions.length === 0">No runs found in <code>experiment/runs</code>.</p>
      </template>
    </section>

    <section v-if="details" class="panel">
      <h2>{{ details.runId }}</h2>
      <div class="meta-grid">
        <div class="metric">
          <span class="metric-label">Plain rows</span>
          <strong>{{ details.counts.plain }}</strong>
        </div>
        <div class="metric">
          <span class="metric-label">Prioritized rows</span>
          <strong>{{ details.counts.prioritized }}</strong>
        </div>
        <div class="metric">
          <span class="metric-label">Compared rows</span>
          <strong>{{ details.counts.compared }}</strong>
        </div>
        <div class="metric metric-up">
          <span class="metric-label">Moved up</span>
          <strong>{{ movedUpCount }}</strong>
        </div>
        <div class="metric metric-down">
          <span class="metric-label">Moved down</span>
          <strong>{{ movedDownCount }}</strong>
        </div>
        <div class="metric metric-flat">
          <span class="metric-label">Unchanged</span>
          <strong>{{ unchangedCount }}</strong>
        </div>
      </div>

      <div class="files">
        <div><strong>Before file:</strong> <code>{{ details.files.baselineRanking }}</code></div>
        <div><strong>After file:</strong> <code>{{ details.files.prioritizationSummary }}</code></div>
      </div>
    </section>

    <section class="panel">
      <div class="table-head">
        <h2>Before vs After</h2>
        <div class="table-controls">
          <label class="inline-toggle">
            <input v-model="onlyVuln" type="checkbox" />
            Only files with findings
          </label>
          <label>
            Sort
            <select v-model="sortMode">
              <option value="after">After rank</option>
              <option value="before">Before rank</option>
              <option value="largestChange">Largest rank change</option>
              <option value="vuln">Most vulnerable</option>
            </select>
          </label>
        </div>
      </div>
      <div v-if="detailsStatus === 'pending'">Loading run details...</div>
      <div v-else-if="detailsStatus === 'error'">{{ detailsError }}</div>
      <div v-else-if="!details || visibleRows.length === 0">No comparison rows found.</div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Path</th>
              <th>Before Rank</th>
              <th>Before Score</th>
              <th>After Rank</th>
              <th>Priority Score</th>
              <th>Tier</th>
              <th>CVSS</th>
              <th>Findings</th>
              <th>Rank Change</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in visibleRows" :key="row.path">
            <tr class="clickable-row" @click="toggleExpanded(row.path)">
              <td><code>{{ row.path }}</code></td>
              <td>{{ row.before?.rank ?? '-' }}</td>
              <td>{{ row.before?.score ?? '-' }}</td>
              <td>{{ row.after?.rank ?? '-' }}</td>
              <td>{{ row.after?.priorityScore ?? '-' }}</td>
              <td>
                <span class="tier-pill">{{ row.after?.priorityTier ?? '-' }}</span>
              </td>
              <td>
                <span :class="['cvss-pill', cvssClass(row.after?.maxCvss)]">{{ row.after?.maxCvss ?? '-' }}</span>
              </td>
              <td>{{ row.after?.vulnFindings ?? '-' }}</td>
              <td>
                <span :class="['trend-pill', `trend-${rankTrend(row.rankChange)}`]">{{ formatRankChange(row.rankChange) }}</span>
              </td>
            </tr>
            <tr v-if="isExpanded(row.path)" class="details-row">
              <td colspan="9">
                <div class="details-grid">
                  <div>
                    <strong>After Why</strong>
                    <p>{{ row.after?.why || '-' }}</p>
                  </div>
                  <div>
                    <strong>Before Why</strong>
                    <p>{{ row.before?.why || '-' }}</p>
                  </div>
                  <div>
                    <strong>LLM</strong>
                    <p>score={{ row.after?.llmScore ?? '-' }}, rank={{ row.after?.llmRank ?? '-' }}, confidence={{ row.after?.llmConfidence ?? '-' }}</p>
                  </div>
                  <div>
                    <strong>Fan-in / Git</strong>
                    <p>fan_in={{ row.after?.meta?.fanIn ?? '-' }} (rank {{ row.after?.meta?.faninRank ?? '-' }}), commits={{ row.after?.meta?.gitCommitsTouched ?? '-' }}, churn={{ row.after?.meta?.gitChurn ?? '-' }}, git_rank={{ row.after?.meta?.gitRank ?? '-' }}</p>
                  </div>
                  <div>
                    <strong>Primary Vulnerability</strong>
                    <p>rule={{ row.after?.meta?.primaryVulnRule || '-' }}, category={{ row.after?.meta?.primaryVulnCategory || '-' }}, severity={{ row.after?.meta?.primaryVulnSeverity || '-' }}, line={{ row.after?.meta?.primaryVulnLine ?? '-' }}, cvss={{ row.after?.meta?.primaryVulnCvss ?? '-' }}</p>
                  </div>
                  <div>
                    <strong>CVSS Vector</strong>
                    <p>{{ row.after?.meta?.maxCvssVector || '-' }}</p>
                  </div>
                </div>
              </td>
            </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>
  </main>
</template>

<style scoped>
:global(body) {
  margin: 0;
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
  background:
    radial-gradient(circle at 15% 0%, rgba(246, 223, 188, 0.35), transparent 42%),
    radial-gradient(circle at 90% 10%, rgba(138, 175, 164, 0.3), transparent 34%),
    #f8f4ee;
  color: #1f2d2f;
}

.page {
  max-width: 1240px;
  margin: 0 auto;
  padding: 22px;
  display: grid;
  gap: 14px;
}

.panel {
  background: rgba(255, 252, 248, 0.85);
  border: 1px solid #decfbd;
  border-radius: 16px;
  padding: 18px;
  box-shadow: 0 10px 22px rgba(83, 52, 20, 0.06);
}

.hero {
  background:
    linear-gradient(120deg, rgba(255, 255, 255, 0.7), rgba(255, 250, 242, 0.85)),
    repeating-linear-gradient(-45deg, rgba(183, 214, 205, 0.14), rgba(183, 214, 205, 0.14) 14px, rgba(255, 255, 255, 0) 14px, rgba(255, 255, 255, 0) 28px);
}

h1,
h2 {
  margin: 0 0 10px;
  font-family: "Source Serif 4", Georgia, serif;
  letter-spacing: 0.2px;
}

.subtitle {
  margin: 0 0 14px;
  max-width: 70ch;
  color: #3b474a;
}

label {
  display: block;
  margin-bottom: 6px;
  font-weight: 600;
}

select {
  width: 100%;
  max-width: 560px;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid #bfa891;
  background: #fffcf8;
  color: #1f2d2f;
}

.meta-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
}

.metric {
  border: 1px solid #ddccb8;
  background: #fffdf9;
  border-radius: 12px;
  padding: 10px;
}

.metric-label {
  display: block;
  font-size: 12px;
  color: #6b5b4a;
  margin-bottom: 4px;
}

.metric-up {
  border-color: #9fc3b7;
}

.metric-down {
  border-color: #e0b2ab;
}

.metric-flat {
  border-color: #cecabf;
}

.files {
  margin-top: 12px;
  display: grid;
  gap: 8px;
  color: #3a3f42;
}

.table-head {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 12px;
  flex-wrap: wrap;
}

.table-controls {
  display: flex;
  gap: 12px;
  align-items: end;
  flex-wrap: wrap;
}

.table-controls select {
  max-width: 210px;
}

.inline-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 0;
  white-space: nowrap;
}

.table-wrap {
  overflow: auto;
  border: 1px solid #ddccb8;
  border-radius: 12px;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 920px;
}

th,
td {
  border-bottom: 1px solid #e7d8c7;
  padding: 10px;
  text-align: left;
  vertical-align: top;
}

thead th {
  background: #f4ece1;
  font-size: 13px;
  letter-spacing: 0.2px;
}

tbody tr:nth-child(odd) {
  background: rgba(255, 251, 245, 0.7);
}

.clickable-row {
  cursor: pointer;
}

.clickable-row:hover {
  background: rgba(170, 191, 185, 0.16);
}

.details-row td {
  background: rgba(247, 240, 231, 0.9);
}

.details-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.details-grid p {
  margin: 4px 0 0;
  color: #364348;
}

.tier-pill,
.cvss-pill,
.trend-pill {
  display: inline-block;
  min-width: 54px;
  text-align: center;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 600;
}

.tier-pill {
  background: #ece6dc;
  color: #4b4132;
}

.cvss-pill {
  border: 1px solid transparent;
}

.cvss-none {
  background: #f0ede8;
  color: #5b5b5b;
}

.cvss-low {
  background: #e8f5eb;
  color: #2c6e36;
  border-color: #bfe1c6;
}

.cvss-medium {
  background: #fff3d8;
  color: #7d5800;
  border-color: #f2d799;
}

.cvss-high {
  background: #ffe6d8;
  color: #8a3900;
  border-color: #f0b991;
}

.cvss-critical {
  background: #ffe3e0;
  color: #9b1414;
  border-color: #e8a4a0;
}

.trend-up {
  background: #e5f5ef;
  color: #22664d;
}

.trend-down {
  background: #fce7e4;
  color: #8a3028;
}

.trend-same {
  background: #ecece7;
  color: #55564e;
}

.trend-na {
  background: #f0ede8;
  color: #7a7267;
}

@media (max-width: 700px) {
  .page {
    padding: 14px;
  }

  .panel {
    padding: 12px;
  }

  .table-controls {
    width: 100%;
  }
}
</style>
