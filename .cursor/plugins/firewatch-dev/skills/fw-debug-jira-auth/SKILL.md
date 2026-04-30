---
name: fw-debug-jira-auth
description: Step-by-step diagnostic workflow for Jira authentication and token issues. Use when firewatch fails with JIRAError on connection, returns 401/403 from Jira, or when tokens need renewal or rotation.
---

# Debug Jira Auth

## Trigger

Firewatch fails during Jira authentication or token-dependent operations. Symptoms include `JIRAError` during `JIRA()` initialization in `jira_base.py`, 401 Unauthorized or 403 Forbidden responses from Jira REST API calls, or CI job failures at the `jira-config-gen` or `report` step with authentication-related errors.

## Diagnostic Workflow

### 1. Verify Config File

The `Jira` class reads credentials from a JSON file specified via `--jira-config-path`. Validate the file structure:

**Required fields**:

| Field | Type | Purpose |
|-------|------|---------|
| `url` | string | Jira server URL (e.g., `https://issues.redhat.com`) |
| `token` | string | API token or PAT |

**Optional fields**:

| Field | Type | Purpose |
|-------|------|---------|
| `email` | string | Presence selects Jira Cloud Basic Auth mode |
| `proxies` | object | HTTP/HTTPS proxy URLs for stage environments |

**Quick checks**:
- Confirm the file is valid JSON (`python -c "import json; json.load(open('<path>'))"`)
- Confirm `url` is a reachable Jira instance
- Confirm `token` is non-empty and does not contain leading/trailing whitespace or newlines
- If the URL contains `stage`, confirm `proxies` is set (the `jira-config-gen` template adds this automatically, but manually-created configs may omit it)

### 2. Identify Auth Mode and Validate Token

The auth mode is determined by the presence of the `email` field in the config file:

| Mode | Config | Auth Method | Token Source |
|------|--------|-------------|--------------|
| Jira Cloud | `email` present | `basic_auth = (email, token)` | Atlassian API token from id.atlassian.com |
| Jira Server/DC | `email` absent | `token_auth = token` | Personal Access Token from Jira user profile |

**Validation via curl**:

Jira Cloud:
```bash
curl -s -o /dev/null -w "%{http_code}" \
  -u "<email>:<token>" \
  "https://<instance>.atlassian.net/rest/api/3/myself"
```

Jira Server/DC:
```bash
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer <token>" \
  "https://<server>/rest/api/3/myself"
```

A `200` confirms the token is valid. A `401` means the token is expired, revoked, or incorrect. A `403` means the token is valid but lacks permissions.

**Common mistakes**:
- Using a Cloud API token without the `email` field (sends as PAT, gets 401)
- Using a Server/DC PAT with the `email` field (sends as Basic Auth, gets 401)
- Copying the token with trailing newlines from `cat` output

### 3. Check CI Secret Mounting

In OpenShift CI (Prow), the Jira token is provisioned as a Kubernetes secret mounted into the pod.

| Variable | Default | Purpose |
|----------|---------|---------|
| `FIREWATCH_JIRA_API_TOKEN_PATH` | `/tmp/secrets/jira/access_token` | Path to the mounted token file |

The CI step script typically runs:
```bash
echo "${JIRA_TOKEN}" > /tmp/token
firewatch jira-config-gen --token-path /tmp/token --server-url "${JIRA_SERVER_URL}"
```

**Quick checks**:
- Verify the token file exists at the expected path and is non-empty
- Confirm the file contains the raw token string (not JSON, not base64-encoded)
- Check for trailing newlines: `wc -l /tmp/secrets/jira/access_token` should return `0` (no newline) or `1` (single trailing newline, which `JiraConfig.token()` strips via `.strip()`)
- Verify the K8s secret is correctly bound in the pod spec for the CI step

### 4. Token Renewal Procedures

**Jira Cloud (Atlassian API tokens)**:
1. Log in to https://id.atlassian.com/manage-profile/security/api-tokens
2. Revoke the expired token if still listed
3. Create a new API token with a descriptive label
4. Note: Atlassian org admins can enforce token expiration policies; check with your org admin if tokens expire unexpectedly soon

**Jira Server/Data Center (PATs)**:
1. Log in to the Jira instance as the service account user (e.g., `firewatch-tool`)
2. Navigate to Profile > Personal Access Tokens
3. Create a new token, setting an appropriate expiration date
4. Note: Server admins can revoke PATs at any time; check with your Jira admin if a token stops working before its expiration date

### 5. CI Secret Rotation

After generating a new token, update the CI secret. No firewatch code changes are needed; the token file path remains the same.

1. Generate the new token in Jira (see step 4)
2. Update the Kubernetes secret in the CI cluster that mounts to `FIREWATCH_JIRA_API_TOKEN_PATH`
3. Trigger a new CI job run to verify the updated token works
4. The `jira-config-gen` command reads the token from the file path at runtime, so the rendered config will pick up the new value automatically

### 6. Common Failure Modes Reference

| Symptom | Likely Cause | Where to Look |
|---------|-------------|---------------|
| `JIRAError` during `Jira.__init__` | Expired or invalid token | Token validation (step 2) |
| `401 Unauthorized` on any Jira call | Token expired, revoked, or wrong auth mode | Auth mode (step 2), renewal (step 4) |
| `403 Forbidden` on specific operations | Token valid but user lacks project permissions | README "Jira User Permissions" section |
| `403 Forbidden` on all operations | Token valid but user not added to the project | Add user to the Jira project under the `Developer` role |
| Connection timeout with stage URL | Missing `proxies` in config | Config file (step 1); ensure `proxies` includes `http://squid.corp.redhat.com:3128` |
| `jira-config-gen` succeeds but operations fail | Wrong auth mode for server type (Cloud token used as PAT or vice versa) | Auth mode (step 2) |
| Empty or missing token file in CI | K8s secret not mounted or wrong path | CI secret mounting (step 3) |
| `click.Abort()` from `jira-config-gen` | Token file unreadable at `--token-path` | File permissions, path correctness |
| Retry exhaustion (3 retries then exception) | `@ignore_exceptions(retry=3)` does not distinguish auth errors from transient failures | Token validation (step 2); the codebase has no special 401 handling |

## Key Source Files

- `src/objects/jira_base.py`: `Jira` class, authentication setup in `__init__`, `_jira_request` for direct REST calls
- `src/jira_config_gen/jira_config_gen.py`: `JiraConfig` class, token file reading, Jinja2 template rendering
- `src/commands/jira_config_gen.py`: CLI options for `jira-config-gen` command
- `src/templates/jira.config.j2`: Jinja2 template with auto-proxy for stage URLs
