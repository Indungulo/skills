# Troubleshooting

Use this reference when EUMDAC commands, imports, authentication, downloads, customisations, subscriptions, or orders fail.

## First Triage

Collect only sanitized information:

```bash
eumdac --version
eumdac --help
eumdac <command> --help
```

Ask for:

```text
Exact command with secrets replaced by placeholders
Full error message with tokens/keys removed
Operating system and shell
Python environment type: uv, venv, conda, system Python, binary release
Whether network access and EO Portal/API credentials are available
Collection ID, product ID, customisation ID, order ID, or subscription tag if relevant
```

## Common Issues

| Symptom | Likely cause | Next step |
| --- | --- | --- |
| `eumdac: command not found` | Not on `PATH`: environment not active, user-tool bin directory not on `PATH`, or not installed | `command -v eumdac`; activate the environment the user names or call `<venv>/bin/eumdac`; check `~/.local/bin` is on `PATH` for tool installs; otherwise install per install.md |
| `eumdac download` never finishes and prints nothing | `--product` received an empty value, for example from an unset shell variable; observed hanging for hours in 3.1.1 | Check the product ID is non-empty before calling, and run under `timeout` |
| `eumdac search` prints nothing for minutes | `--sort` combined with `--bbox`/`--geometry` or a wide time window pages the full result set before limiting (observed in 3.1.1) | Kill it, drop `--sort`, narrow `--time-range`, keep `--limit`, and rerun under `timeout 120` |
| Python import fails | Package installed in different interpreter | Check `python -m pip show eumdac` and `which python` |
| 401/403 errors | Missing/expired/unauthorized credentials | Re-check credential setup; do not print secrets |
| `set-credentials` would overwrite existing credentials | `~/.eumdac/credentials` or `$EUMDAC_CONFIG_DIR/credentials` already exists | Validate with `eumdac token`; replace only after user confirmation |
| Collection not found | Wrong collection ID or no authorization | Run `eumdac describe --filter "<term>"` or verify access |
| No products returned | Time range/filter too narrow or wrong collection | Reduce filters, confirm UTC dates, inspect search options |
| Download incomplete | Network interruption, quota/storage, entry filter mismatch | Retry with `--integrity`, check output path and filters |
| Tailor job stuck/failed | Invalid chain, quota, service-side failure | Check `tailor status`, `tailor log`, and `tailor quota` |
| Subscription downloads too much | Broad filters or missing stop criteria | Tighten collection/time/product filters and output rules |

## Debug Flags

EUMDAC supports:

```bash
eumdac --debug <command> ...
eumdac --trace <command> ...
```

Use debug/trace carefully. They may expose request details or paths; sanitize before sharing output.

## Live-Service Boundary

Do not claim a workflow was validated unless it was actually run with credentials and network access. If only help/import checks were run, say so:

```text
Validated locally against eumdac --help and Python imports. Live EUMETSAT service calls were not run because credentials/network access were not provided.
```
