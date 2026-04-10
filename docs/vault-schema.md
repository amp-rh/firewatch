# Firewatch Jira credentials (Vault KV)

**Vault:** `https://vault.ci.openshift.org`
**Path:** `kv/selfservice/firewatch-tool/jira-credentials`
**Service identity:** `firewatch@redhat.com` (display name: firewatch tool)
**Jira (prod):** `https://redhat.atlassian.net`
**Jira (stage):** `https://stage-redhat.atlassian.net`

Consumers mount this secret and run:

```bash
firewatch jira-config-gen --token-path <mounted-path> --server-url <url> --email <email>
```

## Secret schema

### Fields managed by token rotation

| Field | Type | Description |
|-------|------|-------------|
| `email` | string | Jira account email (`firewatch@redhat.com`). Passed to `firewatch jira-config-gen` as `--email`. |
| `access_token` | string | Production Jira API token. Read from the mounted path given to `--token-path`. |
| `access_token_msi` | string | Copy of `access_token` (kept in sync during rotation). |
| `access_token_stage` | string | Staging-only Jira API token for `stage-redhat.atlassian.net`. Rotated independently from the production token. |
| `expires_at` | string | Production token expiry as ISO 8601 date (`YYYY-MM-DD`). Used only by the token-expiry alert script; **firewatch does not read this field**. |

### Other fields (do not modify during rotation)

| Field | Description |
|-------|-------------|
| `jira_username` | Atlassian account username |
| `jira_password` | Atlassian account password |
| `jira_2fa_recovery_key` | Account 2FA recovery credential |
| `secretsync/target-name` | Secret sync target name (`firewatch-tool-jira-credentials`) |
| `secretsync/target-namespace` | Secret sync target namespace (`test-credentials`) |

### Field formats

- **`email`:** Plain email string.
- **`access_token` / `access_token_msi` / `access_token_stage`:** Opaque secret strings; treat like any API token (no logging, minimal retention in shells).
- **`expires_at`:** ISO 8601 date string. Use `YYYY-MM-DD` for clarity with Atlassian token rotation dates.

## Update fields during rotation

Always use `patch` to avoid overwriting fields this procedure does not manage:

```bash
vault kv patch kv/selfservice/firewatch-tool/jira-credentials \
  access_token='<new-token>' \
  access_token_msi='<new-token>' \
  expires_at='2027-04-06'
```

**Do not use `vault kv put`.** A `put` replaces the entire secret and would destroy the secretsync config, account credentials, and staging token.

## Update the staging token

```bash
vault kv patch kv/selfservice/firewatch-tool/jira-credentials \
  access_token_stage='<new-staging-token>'
```

## `expires_at` and firewatch

`expires_at` exists so a separate **token-expiry alert** can warn before the Jira token lapses. The `firewatch` CLI and `jira-config-gen` flow use only `email` and the token file content (`access_token`).

## Verify after any change

```bash
vault kv get kv/selfservice/firewatch-tool/jira-credentials
```

Confirm all 10 fields are present and unchanged fields were not lost.
