# EWCCLI Infrastructure Commands

Use this reference for direct `ewc infra` OpenStack server workflows.

`ewc infra` is not a general OpenStack administration interface. In `ewccli 0.3.1`, it covers server create/show/list/delete workflows only. It does not expose DNS, S3, Kubernetes, floating DNS records, or DNS zone management commands.

If the request is about images, VM plans/flavours, login/profile, Hub, custom catalogues, troubleshooting, official links, or any non-`ewccli` workflow, return to the routing tables in [SKILL.md](../SKILL.md).

## Safety Boundary

`ewc infra create` and `ewc infra delete` are state-changing OpenStack operations. Confirm profile, server name, target federee, and dry-run expectations before suggesting execution. Do not run live commands without explicit user approval and usable credentials.

## Help Checks

Run the group help before giving exact flags:

```bash
ewc infra --help
```

Some `ewc infra <command> --help` calls initialize profile/OpenStack configuration before printing help and can emit missing-credential errors when no profile or OpenStack config exists. Treat subcommand help as safe only in a configured environment, and sanitize any paths or credential-related output before sharing.

## Profile

`ewc infra` loads a profile with `--profile`; otherwise it uses the default profile.

```bash
ewc infra --profile <profile-name> list
```

`--profile` is an `ewc infra` group option. Put it before the infra subcommand:

```bash
ewc infra --profile <profile-name> list
ewc infra --profile <profile-name> show <server-name>
```

Do not suggest this form for infra commands:

```bash
ewc infra list --profile <profile-name>
```

The profile supplies federee, tenant, application credentials, and SSH key paths unless overridden.

`ewc infra` validates the loaded profile before dispatching to `list`, `show`, `create`, or `delete`. A manually edited profile can fail with missing `ssh_public_key_path` or `ssh_private_key_path` even for `list`; route those cases to [auth-profiles.md](auth-profiles.md) or [troubleshooting.md](troubleshooting.md).

For VM plan/flavour selection, use [vm-plans.md](vm-plans.md). `ewccli 0.3.1` accepts `--flavour-name`, but it does not expose a dedicated `ewc` command to list all available flavours.

## List And Show

List servers created by EWC CLI:

```bash
ewc infra --profile <profile-name> list
```

List all visible servers, including machines not created by EWC CLI:

```bash
ewc infra --profile <profile-name> list --show-all
```

Show one server:

```bash
ewc infra --profile <profile-name> show <server-name>
```

## Create

Dry-run first:

```bash
ewc infra --profile <profile-name> create <server-name> --dry-run
```

Real create template:

```bash
ewc infra --profile <profile-name> create <server-name> \
  --image-name <ewc-virtual-image-name-or-supported-ewccli-selector> \
  --flavour-name <flavour-name> \
  --networks <network-name> \
  --security-groups <security-group-name>
```

Common optional flags include:

```text
--dry-run
--force
--keypair-name / -kp
--image-name / -ig
--flavour-name / -fr
--external-ip
--networks / -n
--security-groups / -sg
--ssh-public-key-path
--ssh-private-key-path
--auth-url / -url
--application-credential-id
--application-credential-secret
```

Do not recommend passing secrets on the command line unless the user explicitly needs non-interactive execution; profiles, `clouds.yaml`, `openrc`, or secret-managed environment variables reduce shell-history exposure.

If a public IP is needed for direct SSH access, include:

```bash
--external-ip
```

## Delete

Dry-run first:

```bash
ewc infra --profile <profile-name> delete <server-name> --dry-run
```

Real delete:

```bash
ewc infra --profile <profile-name> delete <server-name>
```

Use `--force` only when the user explicitly wants to delete a machine that may not have been created by `ewccli`.

## Defaults From Source

The inspected `ewccli 0.3.1` source includes these defaults:

| Setting | ECMWF | EUMETSAT |
| --- | --- | --- |
| Auth URL | `https://auth.os-api.cci1.ecmwf.int:443` | `https://keystone.cloudferro.com:5000` |
| Default CPU image selector | `Rocky-9` | `Rocky-9` |
| Default CPU flavour | `4cpu-4gbmem-30gbdisk` | `eo1.large` |
| Default network | `private` | `private` |
| Default external network | `external-internet` | `external` |
| Default security group | `ssh` | `ssh` |

Treat these as version-specific defaults. `Rocky-9` is an `ewccli` short selector/default, not the dated official image name in the EWC Virtual Images table. For exact official image names, use [vm-images.md](vm-images.md) and copy from the `EWC Virtual Image name` column.

For the complete federee-specific VM plan/flavour lists, use [vm-plans.md](vm-plans.md). Do not infer generic small/medium/large categories beyond the exact names documented there.
