# Firewatch Jira API token rotation (manual)

**Service identity:** firewatch@redhat.com (display name: firewatch tool)  
**Jira:** https://redhat.atlassian.net  
**Vault:** https://vault.ci.openshift.org  
**KV path:** `kv/selfservice/firewatch-tool/jira-credentials`  
**Related:** INTEROP-8976

Secret fields: `email`, `access_token`, `expires_at` (ISO 8601). Tokens are created in the Atlassian account UI; CI consumes them via `firewatch jira-config-gen`.

---

## 1. When to rotate

A daily check monitors `expires_at`. Slack alerts go to **#ocp-ci-firewatch-tool** at **30, 14, 7, 3, and 1** days before expiry.

Rotate **before the 7-day mark** so there is time to verify in CI and fix issues without running against the final deadline.

Atlassian Cloud API tokens have a **maximum lifetime of one year** (policy since December 2024).

---

## 2. Prerequisites

- Vault CLI installed and authenticated against `https://vault.ci.openshift.org` with permission to read and write `kv/selfservice/firewatch-tool/jira-credentials`
- Ability to sign in to the Atlassian account for **firewatch@redhat.com** (or coordinate with someone who can)
- Access to **#ocp-ci-firewatch-tool** on Slack for alerts and confirmation
- A way to trigger or observe a CI job that runs firewatch with Jira (for verification)

---

## 3. Steps

a. **Create a new API token** in Atlassian: [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens). Set expiration to the **maximum allowed (1 year)**. Copy the token once; it may not be shown again.

b. **Note the expiry date** shown in Atlassian after creation. Set `expires_at` in Vault to that moment in **ISO 8601** form.

c. **Update Vault** with all three fields (replace placeholders):

   ```bash
   vault kv put kv/selfservice/firewatch-tool/jira-credentials \
     email="firewatch@redhat.com" \
     access_token="NEW_TOKEN_HERE" \
     expires_at="2027-01-15T12:00:00Z"
   ```

d. **Verify the Vault update:**

   ```bash
   vault kv get kv/selfservice/firewatch-tool/jira-credentials
   ```

   Confirm `email`, `access_token` (masked or as expected), and `expires_at` are correct.

e. **Trigger a test CI job** that uses firewatch (`firewatch jira-config-gen` and Jira usage). Confirm the job completes without Jira auth errors.

f. **Revoke the old token** in the Atlassian API tokens page **after** verification succeeds (skip if it already expired).

g. **Post a confirmation** in **#ocp-ci-firewatch-tool**: rotation done, new expiry date, CI check result, and INTEROP-8976 if you are updating that ticket.

---

## 4. Verification

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

1. Put the prior `access_token` and `expires_at` back with `vault kv put` (same command as in section 3 step c, old values).
2. Run `vault kv get` to confirm.
3. Re-run the CI or manual `firewatch report` check.
4. Fix or re-issue the new token in Atlassian before trying Vault again; revoke any bad or leaked token from the failed attempt.

---

## 6. Troubleshooting

| Issue | What to check |
|-------|----------------|
| **Vault denied** | Your Vault identity needs write access to `kv/selfservice/firewatch-tool/jira-credentials`. Ask platform or secret owners to grant KV access for that path. |
| **Jira 401/403 after rotation** | Token typo when pasting into Vault; wrong account (must be firewatch@redhat.com); token revoked early; or Jira/Atlassian incident. Regenerate token and re-`put` if needed. |
| **Token scope / product access** | Ensure the Atlassian user still has access to **redhat.atlassian.net** and that the token was created under that account. |
| **Account locked or login blocked** | Recover access to firewatch@redhat.com via your org’s Atlassian/Google process before rotating. |

For process or ownership questions, use **#ocp-ci-firewatch-tool** and **INTEROP-8976**.
