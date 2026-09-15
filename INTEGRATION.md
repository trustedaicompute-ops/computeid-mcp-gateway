# ComputeID Integration Guide

**Identity, capability scope, and audit trails for AI agents.**

ComputeID issues a verifiable identity — an **AgentPassport** — to every AI agent in your stack. Each passport carries an issuer-signed registration record, a declared capability list, a server-side audit trail, and instant revocation. Your platform (and your customers) get a clear answer to: *which agent did this, what was it allowed to do, and can we shut it off right now?*

- **Live API:** `https://api.aicomputeid.com`
- **Website:** [compute-id.com](https://compute-id.com)
- **GitHub:** [github.com/trustedaicompute-ops](https://github.com/trustedaicompute-ops)
- **Contact:** praveen.gajjala@compute-id.com

---

## What ComputeID provides (and what it doesn't)

We believe identity infrastructure should be precise about its guarantees.

**Provided today:**

- Server-registered agent identity with a unique passport ID (UUID)
- Issuer-signed registration record (RSA-2048 / SHA-256) created at issuance
- Declared capability lists, stored and checkable server-side per capability
- Server-side audit trail: passport lifecycle events plus any agent actions you log
- Instant revocation — verification and capability checks reflect revoked status immediately
- DevicePassports for GPUs/servers, with admin approval workflow
- Post-quantum dual-signing: every AgentPassport carries a live ML-DSA-65 (FIPS 204) signature alongside RSA-2048, and DevicePassports use ML-DSA-87 — both verifiable offline

**Not provided today (roadmap):**

- Agent-held keys and proof-of-possession (current model is issuer-side attestation)
- Hardware-rooted trust (TPM/TEE attestation)
- Decentralised verification (verification is served by our API)

If your integration depends on something in the second list, talk to us — partner requirements directly shape the roadmap.

---

## Integration option 1 — REST API (any language)

The fastest path. Five endpoints cover the full lifecycle.

### Issue a passport

```bash
curl -X POST https://api.aicomputeid.com/v1/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ResearchAgent",
    "description": "Summarises market research",
    "organization": "Acme Corp",
    "capabilities": ["read", "web_browse", "api_call"]
  }'
```

Response (201):

```json
{
  "passport_id": "128079cb-9aa2-49ac-94ff-5f7c87f4c5a5",
  "name": "ResearchAgent",
  "organization": "Acme Corp",
  "status": "active",
  "public_key": "-----BEGIN PUBLIC KEY-----...",
  "signature": "QeTTEA0G401Iyn1wqQ0eN7+...",
  "signature_algorithm": "RSA-SHA256",
  "capabilities": ["read", "web_browse", "api_call"],
  "issued_at": "2026-06-12T08:03:14.973Z"
}
```

Store the `passport_id` with your agent.

### Verify a passport

```bash
curl https://api.aicomputeid.com/v1/agents/{passport_id}/verify
```

Returns `status` (`active` / `revoked`), `signature_valid`, capabilities, and timestamps.

> **Authorisation rule:** require `status == "active"` **and** `signature_valid == true`. The two fields are independent by design — a revoked passport retains a valid signature because it was legitimately issued.

### Check a specific capability

```bash
curl https://api.aicomputeid.com/v1/agents/{passport_id}/capabilities/web_browse
```

Returns `{"granted": true, "capability": "web_browse", "scope": {}, "bound_at": "..."}` or `{"granted": false, "reason": "capability_not_found"}`. After revocation, every capability returns `{"granted": false, "reason": "passport_revoked"}`.

### Log an agent action

```bash
curl -X POST https://api.aicomputeid.com/v1/agents/{passport_id}/actions \
  -H "Content-Type: application/json" \
  -d '{"action": "web_search", "details": {"query": "GPU prices"}, "outcome": "success"}'
```

### Read an agent's audit trail

```bash
curl https://api.aicomputeid.com/v1/agents/{passport_id}/actions?limit=20
```

### Revoke a passport

```bash
curl -X DELETE https://api.aicomputeid.com/v1/agents/{passport_id}/revoke \
  -H "Content-Type: application/json" \
  -d '{"reason": "Task complete"}'
```

### List all passports

```bash
curl https://api.aicomputeid.com/v1/agents
curl "https://api.aicomputeid.com/v1/agents?status=active"
```

---

## Integration option 2 — Python

A complete working integration in ~30 lines using `requests`:

```python
import requests

API = "https://api.aicomputeid.com"

# 1. Issue a passport when you create an agent
passport = requests.post(f"{API}/v1/agents/register", json={
    "name": "ResearchAgent",
    "organization": "Acme Corp",
    "description": "Summarises market research",
    "capabilities": ["read", "web_browse", "api_call"],
}).json()
passport_id = passport["passport_id"]

# 2. Gate actions on verification + capability
def agent_may(capability: str) -> bool:
    v = requests.get(f"{API}/v1/agents/{passport_id}/verify").json()
    if v.get("status") != "active" or not v.get("signature_valid"):
        return False
    c = requests.get(f"{API}/v1/agents/{passport_id}/capabilities/{capability}").json()
    return c.get("granted", False)

if agent_may("web_browse"):
    run_browse_task()
    # 3. Log what the agent did
    requests.post(f"{API}/v1/agents/{passport_id}/actions", json={
        "action": "web_search",
        "details": {"query": "GPU prices"},
        "outcome": "success",
    })

# 4. Revoke when the agent is done (or misbehaves)
requests.delete(f"{API}/v1/agents/{passport_id}/revoke",
                json={"reason": "Task complete"})
```

**About the `computeid-sdk` package:** the SDK on PyPI (`pip install computeid-sdk`) provides server-backed **DevicePassport** registration and an offline, local-object **AgentPassport** model (useful for prototyping capability logic without network calls). Server-backed AgentPassports — shown above via REST — are being wired into the SDK in the next release. Until then, the REST pattern above is the recommended Python integration for agents.

---

## Integration option 3 — MCP (Claude and MCP-compatible runtimes)

If your stack uses the Model Context Protocol, agents can manage their own identity natively.

```bash
pip install computeid-mcp   # v1.1.0+
```

Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "computeid": {
      "command": "computeid-mcp"
    }
  }
}
```

Tools exposed (all call the live API):

| Tool | Purpose |
|---|---|
| `computeid_status` | API health check |
| `issue_agent_passport` | Register an agent, get a passport |
| `verify_agent_passport` | Status + signature validity + capabilities |
| `check_agent_capability` | Per-capability grant check with reason |
| `log_agent_action` | Append to the agent's audit trail |
| `get_agent_audit_log` | Read an agent's audit trail |
| `revoke_agent_passport` | Revoke immediately |
| `list_agent_passports` | List all agents |
| `register_device` / `list_devices` / `approve_device` / `revoke_device` | DevicePassports |
| `generate_audit_summary` | Data summary across agents, devices, logs |

Trust-level presets (`restricted`, `standard`, `elevated`, `autonomous`) map to explicit capability lists — or pass your own `capabilities` array.

---

## Integration option 4 — CLI

```bash
pip install computeid-cli
computeid status            # check API connection
computeid login             # admin login
computeid devices list      # manage DevicePassports
```

The CLI currently focuses on device and admin workflows; agent commands track the API.

---

## Recommended integration pattern

For a platform running agents on behalf of customers:

1. **Issue at creation.** When a customer deploys an agent, register it and store the `passport_id` alongside the agent record. Scope capabilities to what that agent actually needs.
2. **Gate at the boundary.** Before privileged actions (external API calls, code execution, spawning agents), check `verify` + `check_capability`. Cache for seconds, not hours — revocation should bite fast.
3. **Log meaningful actions.** Not every token — every consequential act: external calls, sends, executions. This becomes your customer-facing audit trail and supports record-keeping obligations such as EU AI Act Article 12.
4. **Revoke on offboarding or anomaly.** Revocation is immediate and permanent; verification reflects it on the next check.

---

## Licensing

- **Free tier** — evaluate with a small number of agents and devices at no cost.
- **Startup tier** — $199/month.
- **Platform / OEM partnerships** — if you build ComputeID in as the identity layer for your customers' agents, we offer partner licensing at a significant discount to standard rates. Contact us.

---

## Support

- Email: praveen.gajjala@compute-id.com
- GitHub issues: [github.com/trustedaicompute-ops](https://github.com/trustedaicompute-ops)
- Website: [compute-id.com](https://compute-id.com)

*ComputeID — identity infrastructure for the agentic AI era.*
