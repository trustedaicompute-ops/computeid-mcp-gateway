# ComputeID MCP Server

Give Claude and any MCP-compatible AI the ability to issue cryptographic identities to AI agents natively.

## What it does

Once installed, Claude can:
- **Issue AgentPassports** to any AI agent it spawns or works with
- **Verify agent identity** before accepting work from another agent
- **Log every action** to an immutable audit trail automatically
- **Revoke agents instantly** if they behave unexpectedly
- **Issue DevicePassports** (RSA-2048 + ML-DSA-87) for GPU servers, robots, drones and other devices
- **Summarise audit data** to support record-keeping (e.g. EU AI Act Article 12)

## Install

```
pip install computeid-mcp
```

## Configure Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "computeid": {
      "command": "python",
      "args": ["-m", "computeid_mcp"],
      "env": {
        "COMPUTEID_API_URL": "https://api.aicomputeid.com",
        "COMPUTEID_API_KEY": "your-api-key"
      }
    }
  }
}
```

The key is sent as the `X-API-Key` header (the API does not accept `Authorization: Bearer`). `COMPUTEID_TOKEN` is still read as a fallback for existing configs, but it must hold an API key.

## Tools available

| Tool | Description |
|------|-------------|
| `computeid_status` | Check API health |
| `issue_agent_passport` | Issue a cryptographic identity to an AI agent |
| `verify_agent_passport` | Verify an agent's identity |
| `log_agent_action` | Log an action to the immutable audit trail |
| `revoke_agent_passport` | Instantly revoke an agent |
| `list_agent_passports` | List all agents in your organisation |
| `get_agent_audit_log` | Get full audit trail for an agent |
| `check_agent_capability` | Check whether an agent holds a capability |
| `register_device` | Issue a DevicePassport (active immediately) |
| `list_devices` | List your DevicePassports |
| `revoke_device` | Revoke a DevicePassport |
| `generate_audit_summary` | Data summary across agents, devices and logs |
| `get_audit_logs` | Your account's audit logs |

## Docs

compute-id.com | hello@compute-id.com
