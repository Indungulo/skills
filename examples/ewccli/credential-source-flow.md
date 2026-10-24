# Credential Source To EWCCLI Profile Flow

## User Prompt

```text
How do I authenticate ewccli with the credentials EWC sends me?
```

## Expected Agent Behavior

- Route to `auth-profiles.md`.
- Explain the sequence:
  - Request OpenStack application credentials through the official EWC KB/support process.
  - EWC provides credential material such as `openrc` and/or `clouds.yaml`.
  - The user configures one credential source locally.
  - `ewc login` consumes that source or prompts for credentials.
  - `ewc login` writes only the `ewccli` profile under `$HOME/.ewccli/profiles`.
- Do not say `ewc login` creates, installs, writes, or configures `openrc` or `clouds.yaml`.
- Do not ask the user to paste credential files, application credential IDs, or secrets.

## Safe Response Shape

```text
Workflow type: login/profile.

1. Request OpenStack application credentials using the official EWC KB process:
https://confluence.ecmwf.int/display/EWCLOUDKB/EWC+OpenStack+API+access+-+How+to+request+Openstack+Application+Credentials

2. EWC provides credential files such as `openrc` and/or `clouds.yaml`.

3. Configure one credential source locally:
- install the received `clouds.yaml`, or
- source the received `openrc`, or
- use secret-managed environment variables, or
- let `ewc login` prompt for values.

4. Run `ewc login` to create the ewccli profile.

`ewc login` consumes existing credential sources; it does not create or configure `openrc` or `clouds.yaml`.
```
