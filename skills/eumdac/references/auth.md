# Authentication And Credentials

Use this reference for credential safety, `set-credentials`, token checks, Python authentication, and subscription credentials.

## Credential Safety

EUMDAC Data Store authentication uses an EO Portal consumer key and consumer secret. Never echo real values in answers, command logs, shell history examples, or committed files.

`eumdac set-credentials` writes credentials to the local EUMDAC configuration. In `eumdac 3.1.1`, the default path is:

```text
~/.eumdac/credentials
```

If `EUMDAC_CONFIG_DIR` is set, the credentials path becomes:

```text
$EUMDAC_CONFIG_DIR/credentials
```

Before recommending or running `set-credentials`, check whether credentials already exist:

```bash
python - <<'PY'
import os
from pathlib import Path

config_dir = Path(os.environ.get("EUMDAC_CONFIG_DIR", Path.home() / ".eumdac"))
credentials = config_dir / "credentials"
print(credentials)
print("exists" if credentials.exists() else "missing")
PY
```

If the file exists, do not overwrite it by default. Validate existing credentials with:

```bash
eumdac token >/dev/null
```

`eumdac token` writes the validity line ("The following token is valid until ...") to stderr and the bearer token itself to stdout. Redirecting stdout keeps the token out of the session and logs while the validity line still shows; `| head -1` would print the token, not the validity line. Use `eumdac token 2>&1 >/dev/null` to capture the validity line in a variable.

Only suggest `set-credentials` when the file is missing, invalid, or the user explicitly asks to replace credentials. The user runs this command themselves, in their own terminal, with their real key and secret; the agent never runs it with real values and never asks the user to paste secrets into the chat. The user should avoid shell history capture, for example a leading space with `HISTCONTROL=ignorespace` set, or the shell's equivalent. Use placeholders in any command shown here:

```bash
eumdac set-credentials "<consumer-key>" "<consumer-secret>"
eumdac token >/dev/null
```

If replacing credentials, warn that the local credentials file will be overwritten.

`eumdac token --force` revokes the current token and can affect other processes using the same credentials. Warn before suggesting it.

## Python Authentication

Use placeholders for examples:

```python
import eumdac

credentials = ("<consumer-key>", "<consumer-secret>")
token = eumdac.AccessToken(credentials)
```

`AccessToken(credentials, validity=86400, cache=True)` is the installed `eumdac 3.1.1` signature. The default validity is one day.

## Subscription Credentials

Subscriptions have their own credential command. The user runs this themselves, in their own terminal, with their real username and password; the agent never runs it with real values and never asks the user to paste secrets into the chat. The user should avoid shell history capture, for example a leading space with `HISTCONTROL=ignorespace` set, or the shell's equivalent.

```bash
eumdac subscribe set-credentials "<username>" "<password>"
```

Treat subscription usernames/passwords as secrets too. Subscription credentials are stored under the EUMDAC config directory at:

```text
~/.eumdac/subscriptions/credentials
```

or, when `EUMDAC_CONFIG_DIR` is set:

```text
$EUMDAC_CONFIG_DIR/subscriptions/credentials
```

Check for that file before overwriting subscription credentials.
