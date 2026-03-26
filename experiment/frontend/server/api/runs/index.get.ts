import { join } from 'node:path'
import { getRunDirectories, RUNS_DIR, safeReadJson, summarizeManifest } from '../../utils/runs'

export default defineEventHandler(async () => {
  const runIds = await getRunDirectories()

  const runs = await Promise.all(
    runIds.map(async (runId) => {
      const manifest = await safeReadJson(join(RUNS_DIR, runId, 'manifest.json'))
      return {
        runId,
        ...summarizeManifest(manifest),
      }
    }),
  )

  return {
    runsDir: RUNS_DIR,
    count: runs.length,
    runs,
  }
})
