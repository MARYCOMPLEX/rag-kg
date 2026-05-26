# Integration Log

This file records frontend-backend integration issues, fixes, and verification status.

Use this log during local integration, E2E testing, and contract verification. Every issue should reference the related GitHub Issue when one exists.

## Status Values

| Status | Meaning |
| --- | --- |
| `open` | Issue has been found and still needs investigation or work. |
| `in-progress` | An Agent is actively fixing the issue. |
| `fixed` | A fix has been implemented. |
| `verified` | The fix has passed integration or E2E verification. |
| `wont-fix` | The team decided not to change behavior. |

## Log Template

```markdown
## <YYYY-MM-DD HH:mm> - <short issue title>

- Time:
- Agent:
- Issue:
- Cause:
- Fix status:
```

## Logs

## 2026-05-27 03:30 - Frontend mock default library removed

- Time: 2026-05-27 03:30 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: Frontend routing, library state, document route fallback, and create-library modal still assumed the mock `graphrag-survey` library exists. OpenAPI still has `paths: {}`, so full real API integration is blocked pending backend contracts.
- Fix status: fixed
- Verification:
  - `pnpm typecheck`: passed.
  - `pnpm build`: passed.
