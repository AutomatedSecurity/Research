import { promises as fs } from 'node:fs'
import { basename, join, resolve } from 'node:path'

type ManifestLike = {
  project?: string
  pr_url?: string
  pr_files_count?: number
  steps?: Record<string, unknown>
}

const FRONTEND_ROOT = process.cwd()
export const RUNS_DIR = resolve(FRONTEND_ROOT, '../runs')

export async function safeReadJson<T>(filePath: string): Promise<T | null> {
  try {
    const text = await fs.readFile(filePath, 'utf-8')
    return JSON.parse(text) as T
  } catch {
    return null
  }
}

export async function directoryExists(path: string): Promise<boolean> {
  try {
    const stat = await fs.stat(path)
    return stat.isDirectory()
  } catch {
    return false
  }
}

export async function fileExists(path: string): Promise<boolean> {
  try {
    const stat = await fs.stat(path)
    return stat.isFile()
  } catch {
    return false
  }
}

export async function getRunDirectories(): Promise<string[]> {
  if (!(await directoryExists(RUNS_DIR))) {
    return []
  }

  const entries = await fs.readdir(RUNS_DIR, { withFileTypes: true })
  const runs = entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name)

  const withMtime = await Promise.all(
    runs.map(async (name) => {
      const stat = await fs.stat(join(RUNS_DIR, name))
      return { name, mtimeMs: stat.mtimeMs }
    }),
  )

  withMtime.sort((a, b) => b.mtimeMs - a.mtimeMs)
  return withMtime.map((item) => item.name)
}

export function resolveRunDir(runId: string): string | null {
  if (!runId || runId.includes('/') || runId.includes('..')) {
    return null
  }

  const resolved = resolve(RUNS_DIR, runId)
  if (basename(resolved) !== runId) {
    return null
  }
  return resolved
}

export function summarizeManifest(manifest: ManifestLike | null) {
  return {
    project: manifest?.project ?? null,
    prUrl: manifest?.pr_url ?? null,
    prFilesCount: manifest?.pr_files_count ?? null,
    steps: {
      fanin: Boolean(manifest?.steps?.fanin),
      git_history: Boolean(manifest?.steps?.git_history),
      vulnerabilities: Boolean(manifest?.steps?.vulnerabilities),
      llm: Boolean(manifest?.steps?.llm),
      prioritization: Boolean(manifest?.steps?.prioritization),
    },
  }
}
