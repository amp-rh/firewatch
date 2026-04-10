# Firewatch Jira API token rotation (manual)

**Service identity:** `firewatch@redhat.com` (display name: firewatch tool)
**Jira (prod):** <https://redhat.atlassian.net>
**Jira (stage):** <https://stage-redhat.atlassian.net>
**Vault:** <https://vault.ci.openshift.org>
**KV path:** `kv/selfservice/firewatch-tool/jira-credentials`
**Related:** INTEROP-8976

Managed fields: `email`, `access_token`, `access_token_msi`, `access_token_stage`, `expires_at` (ISO 8601). The secret also contains other fields (account credentials, secretsync config) that this procedure does not modify. Tokens are created in the Atlassian account UI; CI consumes them via `firewatch jira-config-gen`.

API tokens are **account-scoped**, not instance-scoped. A token created for the `firewatch@redhat.com` account works against every Atlassian Cloud instance the account can access (production, staging, etc.).

---

## 1. When to rotate

A daily check monitors `expires_at`. Slack alerts go to **#ocp-ci-firewatch-tool** at **30, 14, 7, 3, and 1** days before expiry.

Rotate **before the 7-day mark** so there is time to verify in CI and fix issues without running against the final deadline.

Atlassian Cloud API tokens have a **maximum lifetime of one year** (policy since December 2024).

---

## 2. Prerequisites

- Vault CLI installed; authenticate with `vault login -method=oidc` (tokens last 1 hour)
- Write access to `kv/selfservice/firewatch-tool/jira-credentials`
- Ability to sign in to the Atlassian account for **`firewatch@redhat.com`** (or coordinate with someone who can)
- Access to **#ocp-ci-firewatch-tool** on Slack for alerts and confirmation
- A way to trigger or observe a CI job that runs firewatch with Jira (for verification)

---

## 3. Steps

a. **Create a new API token** in Atlassian: [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens). Set expiration to the **maximum allowed (1 year)**. Copy the token once; it may not be shown again.

b. **Note the expiry date** shown in Atlassian after creation.

c. **Update Vault** using `patch` (preserves fields this procedure does not manage):

   ```bash
   vault kv patch kv/selfservice/firewatch-tool/jira-credentials \
     access_token="NEW_TOKEN_HERE" \
     access_token_msi="NEW_TOKEN_HERE" \
     expires_at="2027-01-15"
   ```

   **Do not use `vault kv put` here.** A `put` replaces the entire secret and would destroy other fields (secretsync config, account credentials, staging token).

d. **Verify the Vault update:**

   ```bash
   vault kv get kv/selfservice/firewatch-tool/jira-credentials
   ```

   Confirm `access_token`, `access_token_msi`, and `expires_at` are updated. Confirm other fields (`email`, `access_token_stage`, `secretsync/*`, etc.) are unchanged.

e. **Verify against staging** before waiting for CI:

   ```bash
   curl -s -u "firewatch@redhat.com:NEW_TOKEN_HERE" \
     https://stage-redhat.atlassian.net/rest/api/2/myself | python3 -m json.tool
   ```

   A successful response confirms the token is valid. Staging has production data and the same permissions.

f. **Trigger a test CI job** that uses firewatch (`firewatch jira-config-gen` and Jira usage). Confirm the job completes without Jira auth errors.

g. **Revoke the old token** in the Atlassian API tokens page **after** verification succeeds (skip if it already expired).

h. **Post a confirmation** in **#ocp-ci-firewatch-tool**: rotation done, new expiry date, CI check result, and INTEROP-8976 if you are updating that ticket.

---

## 4. Verification

- **Staging:** Run `curl -u "firewatch@redhat.com:TOKEN" https://stage-redhat.atlassian.net/rest/api/2/myself` and confirm a 200 with the correct account.
- **CI:** Open a recent successful job that uses firewatch Jira integration; confirm no 401/403 from Jira in logs.
- **Manual:** Generate config as CI does, then run firewatch against Jira, for example:

  ```bash
  firewatch jira-config-gen  # or your pipeline-equivalent step
  firewatch report ...        # use the same flags/env your jobs use
  ```

  A successful report (or equivalent Jira touch) confirms the new token.

---

## 5. Rollback

If the new token fails after the Vault update, the **previous token stays valid until you revoke it** in Atlassian.

1. Put the prior `access_token`, `access_token_msi`, and `expires_at` back with `vault kv patch` (same command form as step 3c, old values).
2. Run `vault kv get` to confirm.
3. Re-run the CI or manual `firewatch report` check.
4. Fix or re-issue the new token in Atlassian before trying Vault again; revoke any bad or leaked token from the failed attempt.

---

## 6. Troubleshooting

| Issue | What to check |
|-------|----------------|
| **Vault denied** | Your Vault identity needs write access to `kv/selfservice/firewatch-tool/jira-credentials`. Ask platform or secret owners to grant KV access for that path. |
| **Jira 401/403 after rotation** | Token typo when pasting into Vault; wrong account (must be `firewatch@redhat.com`); token revoked early; or Jira/Atlassian incident. Regenerate token and re-patch if needed. |
| **Token scope / product access** | Ensure the Atlassian user still has access to **redhat.atlassian.net** and that the token was created under that account. |
| **Account locked or login blocked** | Recover access to `firewatch@redhat.com` via your org's Atlassian/Google process before rotating. |

For process or ownership questions, use **#ocp-ci-firewatch-tool** and **INTEROP-8976**.
