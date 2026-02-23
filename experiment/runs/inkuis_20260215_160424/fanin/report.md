# Fan-in Ranking

- Project: `/Users/matar/WORK/inkuis`
- Engine: `codeql`
- Entry points detected: `23`
- Modules ranked: `29`

## Top Modules

| Rank | Module | Fan-in |
|---:|---|---:|
| 1 | `server/models/User.ts` | 15 |
| 2 | `server/models/Event.ts` | 13 |
| 3 | `server/utils/auth.ts` | 5 |
| 4 | `server/validation/eventSchemas.ts` | 3 |
| 5 | `utils/categoryHierarchy.ts` | 2 |
| 6 | `server/api/analytics/index.ts` | 1 |
| 7 | `server/api/auth/login.ts` | 1 |
| 8 | `server/api/auth/logout.ts` | 1 |
| 9 | `server/api/auth/me.ts` | 1 |
| 10 | `server/api/auth/register.ts` | 1 |
| 11 | `server/api/chatbot/index.post.ts` | 1 |
| 12 | `server/api/events/[id].delete.ts` | 1 |
| 13 | `server/api/events/[id].get.ts` | 1 |
| 14 | `server/api/events/[id].put.ts` | 1 |
| 15 | `server/api/events/[id]/attend.post.ts` | 1 |
| 16 | `server/api/events/index.post.ts` | 1 |
| 17 | `server/api/events/index.ts` | 1 |
| 18 | `server/api/geocode.ts` | 1 |
| 19 | `server/api/health.ts` | 1 |
| 20 | `server/api/public/v1/events/[id].delete.ts` | 1 |

## Notes

- Fan-in is file-level: number of distinct entrypoint files that can reach a module through import edges.
- Reachability edges were extracted via CodeQL import resolution on a CodeQL database.