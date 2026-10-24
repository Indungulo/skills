# Create An EWCCLI Login Profile

## Prompt

Show me how to create an EWC CLI profile for my EUMETSAT tenancy without exposing secrets.

## Expected Agent Behavior

- Use the `ewccli` skill and load `auth-profiles.md`.
- Use `https://www.europeanweather.cloud/` for the European Weather Cloud website.
- For OpenStack application credential requests, point to the official EWC Knowledge Base article and explain the support-ticket process.
- Explain that EWC provides `openrc` and/or `clouds.yaml` after the credential request, and those are credential sources used before `ewc login`.
- Explain that `ewc login` stores profiles under `$HOME/.ewccli/profiles`.
- Explain that `ewc login` consumes existing OpenStack credential sources or prompts for credentials; it does not create, install, or configure `clouds.yaml` or `openrc`.
- Do not use `ewc hub list` as authentication validation; it is catalogue discovery and can work unauthenticated.
- If validation is requested, distinguish local profile creation from live OpenStack checks such as `ewc infra --profile <profile-name> list`.
- Use placeholders for application credential ID and secret.
- Mention federee choices: `EUMETSAT` or `ECMWF`.
- Mention tenant name shape: `<memberstate>-<organization>-<projectname>`.
- Do not invent a concrete tenant name.
- Do not print or request the user to paste secrets into the chat.
- Ask the user to confirm before replacing or deleting existing profile entries.

## Command Pattern

```bash
ewc login \
  --profile <profile-name> \
  --federee EUMETSAT \
  --tenant-name <tenant-name> \
  --ssh-public-key-path $HOME/.ssh/id_rsa.pub \
  --ssh-private-key-path $HOME/.ssh/id_rsa
```

Configure a protected `clouds.yaml`, source `openrc`, or set secret-managed environment variables before running `ewc login`; otherwise let `ewc login` prompt for credential values with hidden input.

## Expected Response Shape

- Workflow type: login/profile.
- Prerequisites: installed `ewccli`, EWC tenancy, OpenStack application credential, SSH key pair.
- Credential safety: placeholders and no secret echoing.
- Commands: interactive and explicit alternatives.
- Validation status: local help checks only unless user authorizes login.
