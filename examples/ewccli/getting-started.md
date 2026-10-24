# Getting Started With EWCCLI

## User Prompt

```text
How do I get started with EWC CLI?
```

## Expected Agent Behavior

- Route to `install.md`, `auth-profiles.md`, and only load `vm-images.md` if mentioning image names.
- Do not invent a tenant name. Use `<memberstate>-<organization>-<projectname>`.
- Do not provide concrete tenant-name examples; plausible-looking tenant names can be real and access-sensitive.
- Explain tenant parts:
  - `memberstate`: member state identifier, such as `de`, `int`, or `it`.
  - `organization`: organization identifier.
  - `projectname`: project identifier.
- For OpenStack application credentials, point to the official KB article and EWC Support Portal process.
- Keep the credential story in order: request application credentials through the official EWC KB/support process, use the received `openrc` or `clouds.yaml` as an OpenStack credential source, then run `ewc login` to create the `ewccli` profile.
- Make clear that `ewc login` consumes existing credential sources or prompts for values; it does not create, install, or configure `openrc` or `clouds.yaml`.
- Do not use `ewc hub list` as login/authentication validation; it is catalogue discovery and can work unauthenticated.
- For live OpenStack credential validation, suggest `ewc infra --profile <profile-name> list` only with a clear note that it is a live call.
- For tenant-name questions, remind the user of the convention and direct them to EWC Support if they do not remember it.
- Do not present `openrc`, `clouds.yaml`, OpenStack project fields, shell variables, or existing `ewccli` profiles as authoritative tenant-name sources.
- Never ask the user to paste full credential files.
- Do not invent image names. If image names are mentioned, point to the official EWC Virtual Images page and say to use the `EWC Virtual Image name` column.
- If explaining `Rocky-9`, call it an `ewccli` short selector/default, not an official dated EWC Virtual Image name.

## Safe Response Shape

```text
Workflow type: install/login/profile.

1. Install and verify:

python -m pip install 'ewccli==0.3.1'
ewc --help
ewc version

2. Request OpenStack application credentials using the official EWC KB process:
https://confluence.ecmwf.int/display/EWCLOUDKB/EWC+OpenStack+API+access+-+How+to+request+Openstack+Application+Credentials

The tenant name should be your real `<memberstate>-<organization>-<projectname>` tenant.

3. Use the credential files received from EWC Support as OpenStack credential sources: install the received `clouds.yaml`, source the received `openrc`, set secret-managed environment variables, or use interactive hidden prompts during login. `ewc login` does not create or configure `clouds.yaml` or `openrc`.

If you do not remember your tenant name, use the `<memberstate>-<organization>-<projectname>` convention to recognize the assigned value, or ask EWC Support.

4. Run:

ewc login

5. Catalogue discovery, not auth validation:

ewc hub list

6. Optional live OpenStack credential check:

ewc infra --profile <profile-name> list

For VM images, use:
https://confluence.ecmwf.int/display/EWCLOUDKB/EWC+Virtual+Images+Available

Copy exact names from the `EWC Virtual Image name` column.
```
