# EWCCLI Examples

These examples are sanitized prompt scenarios for the `ewccli` skill. They are not live-current claims about available EWC Community Hub items or deployed infrastructure.

Do not record OpenStack application credential IDs, application credential secrets, private SSH keys, encoded SSH keys, profile files, or cloud account details in examples.

## Scenarios

| File | Scenario | What it tests |
| --- | --- | --- |
| [install-verify.md](install-verify.md) | Install and verify `ewccli` safely | Isolated install, Python version, credential-free CLI checks |
| [getting-started.md](getting-started.md) | Start using EWC CLI | Install, credentials, tenant-name pattern, no invented image names |
| [login-profile.md](login-profile.md) | Prepare an EWC login profile | Credential placeholders, profile safety, SSH key checks |
| [credential-source-flow.md](credential-source-flow.md) | Use received EWC credential files | Support request, `openrc`/`clouds.yaml` as credential sources, `ewc login` profile creation |
| [tenant-name-discovery.md](tenant-name-discovery.md) | Explain tenant-name convention | Tenant-name convention and EWC Support fallback |
| [profile-edge-cases.md](profile-edge-cases.md) | Diagnose profile and infra command edge cases | Typos, infra `--profile` placement, incomplete manual profiles |
| [hub-deploy-dry-run.md](hub-deploy-dry-run.md) | Inspect and dry-run a Community Hub item | `hub list/show/deploy`, required item inputs, dry-run-first behavior |
| [vm-flavours.md](vm-flavours.md) | Answer available VM flavour questions | Federee-specific official lists, ewccli defaults, no invented categories |
| [custom-catalogue.md](custom-catalogue.md) | Test a custom Hub catalogue | Catalogue shape, `--path-to-catalog`, local item validation |
| [unsupported-commands.md](unsupported-commands.md) | Respond to unsupported EWC CLI requests | Unsupported-command boundary, verified official links when available, no invented service guidance |

## Safe Validation Boundary

Examples should prefer `ewc --help`, `ewc version`, `ewc hub --help`, `ewc infra --help`, `ewc hub list`, and dry-run commands. Do not include live deployment logs unless they are sanitized and clearly marked as observed examples.
