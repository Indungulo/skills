# Feature DB Client Examples

These examples are sanitized scenarios for the `feature-db-client` skill. They are intended as quickstart
scenarios and regression prompts.

Do not treat row counts or feature-type names as current results. Re-run the commands with credentials
and an authorized Feature API endpoint when current data matters.

## Scenarios

| File | Scenario | What it tests |
| --- | --- | --- |
| [prod-default-write.md](prod-default-write.md) | Save features without a stated environment | Prod-is-default trap, environment confirmation, write gating |
| [read-only-query.md](read-only-query.md) | Query features in a bounding box | Reference-data lookup, feature-type disambiguation, read-only boundary |

## Safe Validation Boundary

The examples avoid recording secrets and real endpoints. Keep API keys and authorized Feature API URLs
out of notes and logs; use placeholders in their place.
