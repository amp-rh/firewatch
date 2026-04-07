# Firewatch Jira credentials (Vault KV)

**Vault:** `https://vault.ci.openshift.org`  
**Path:** `kv/selfservice/firewatch-tool/jira-credentials`  
**Service identity:** `firewatch@redhat.com` (display name: firewatch tool)  
**Jira:** `https://redhat.atlassian.net`

Consumers mount this secret and run:

```bash
firewatch jira-config-gen --token-path <mounted-path> --server-url <url> --email <email>
```

## Secret schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | yes | Jira account email (e.g. `firewatch@redhat.com`). Passed to `firewatch jira-config-gen` as `--email`. |
| `access_token` | string | yes | Jira API token for that account. Read from the mounted path given to `--token-path`. |
| `expires_at` | string | yes | Token expiry as an ISO 8601 date (calendar date is enough, e.g. `2027-04-06`). Used only by the token-expiry alert script; **firewatch does not read this field**. |

### Field formats

- **`email`:** Plain email string, no quotes in Vault values unless your shell requires them for `vault kv put`.
- **`access_token`:** Opaque secret string; treat like any API token (no logging, minimal retention in shells).
- **`expires_at`:** ISO 8601 date string. Prefer `YYYY-MM-DD` for clarity with Atlassian token rotation dates.

## Set or update the full secret

Replace placeholders before running:

```bash
vault kv put kv/selfservice/firewatch-tool/jira-credentials \
  email='firewatch@redhat.com' \
  access_token='<jira-api-token>' \
  expires_at='2027-04-06'
```

This overwrites the secret at that path with exactly these keys. Other keys on the same secret, if any, are removed unless you include them in the same `put`.

## `expires_at` and firewatch

`expires_at` exists so a separate **token-expiry alert** can warn before the Jira token lapses. The `firewatch` CLI and `jira-config-gen` flow use only `email` and the token file content (`access_token`).

## Migration: add `expires_at` without losing existing fields

**Preferred: patch (KV v2)**

Adds or updates only `expires_at`; leaves `email` and `access_token` as they are.

```bash
vault kv patch kv/selfservice/firewatch-tool/jira-credentials expires_at='2027-04-06'
```

If `patch` is unavailable, use one of the options below.

**Full put with known values**

Re-run the full `vault kv put` from the previous section with the same `email` and `access_token` values plus the new `expires_at`.

**Vault UI**

Open the secret, add key `expires_at` with value `YYYY-MM-DD`, save. Confirm `email` and `access_token` are unchanged.

After migration, confirm:

```bash
vault kv get kv/selfservice/firewatch-tool/jira-credentials
```

You should see `email`, `access_token`, and `expires_at`.
