# EUMDAC Examples

These examples are sanitized from real prompt/response notes. They are intended as quickstart scenarios and regression prompts for the `eumdac` skill.

Do not treat observed product IDs or dates as current results. Re-run the commands with credentials and network access when current data matters.

## Scenarios

| File | Scenario | What it tests |
| --- | --- | --- |
| [install-verify.md](install-verify.md) | Install and verify EUMDAC safely | Isolated install, credential safety, CLI/Python verification |
| [msg-frm-search.md](msg-frm-search.md) | Search MSG Fire Risk Map products | Discovery, collection description, product-type/satellite filters |
| [fire-detections-spain.md](fire-detections-spain.md) | Interpret "fire detections" for Spain | Correcting product intent, bbox filtering, choosing active-fire collections |
| [fci-hrfi-turkey-download.md](fci-hrfi-turkey-download.md) | Two days of FCI HRFI over Turkey | Large-download risk, bbox-vs-cropping behavior, storage confirmation |
| [snow-products.md](snow-products.md) | Find snow-related products | Discovery by wildcard filters, latest search template |
| [search-hang-timeout.md](search-hang-timeout.md) | Spatially filtered search hangs | No `--sort` with `--bbox`, shell timeouts on live calls, kill-and-narrow instead of waiting |
| [fci-hrfi-subscription.md](fci-hrfi-subscription.md) | Subscribe to FCI HRFI | Subscription setup, tag usage, continuous download safety |

## Safe Validation Boundary

The examples avoid recording secrets. If an example uses live EUMDAC commands, keep token values, consumer keys, consumer secrets, and subscription credentials out of notes and logs.
