#!/usr/bin/env python3
"""
ComputeID MCP Server
Lets Claude and any MCP-compatible AI issue AgentPassports,
manage DevicePassports, and verify identities natively.

All agent tools call the live ComputeID API. Tool output reflects
actual API responses — nothing is simulated.

Install: pip install computeid-mcp
Usage in Claude Desktop: add to claude_desktop_config.json
"""

import asyncio
import json
import os
import sys
import httpx
from datetime import datetime
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# ── CONFIG ────────────────────────────────────────────────────────────────────
API_URL = os.getenv("COMPUTEID_API_URL", "https://api.aicomputeid.com")
# The API authenticates with X-API-Key only. COMPUTEID_TOKEN is still read
# for existing configs that put an API key there.
API_KEY = os.getenv("COMPUTEID_API_KEY") or os.getenv("COMPUTEID_TOKEN", "")

server = Server("computeid")

# Trust levels are convenience presets that map to explicit capability lists.
# The capability list is what is actually stored and enforced server-side.
TRUST_LEVEL_CAPABILITIES = {
    "restricted": ["read"],
    "standard": ["read", "web_browse", "api_call"],
    "elevated": ["read", "web_browse", "api_call", "code_execute"],
    "autonomous": ["read", "web_browse", "api_call", "code_execute", "spawn_agents"],
}

# ── HELPERS ───────────────────────────────────────────────────────────────────

def get_headers():
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h

async def api_get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{API_URL}{path}", headers=get_headers())
        return r.json()

async def api_post(path: str, data: dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{API_URL}{path}", json=data, headers=get_headers())
        return r.json()

async def api_delete(path: str, data: dict = None) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.request("DELETE", f"{API_URL}{path}", json=data or {}, headers=get_headers())
        return r.json()

def fmt_result(data: dict, success_msg: str = "") -> str:
    if isinstance(data, dict) and "error" in data:
        return f"Error: {data['error']}"
    if success_msg:
        return f"{success_msg}\n\n{json.dumps(data, indent=2, default=str)}"
    return json.dumps(data, indent=2, default=str)

# ── TOOLS ─────────────────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [

        # ── STATUS ──────────────────────────────────────────────────────────
        types.Tool(
            name="computeid_status",
            description="Check ComputeID API health and connection status. Use this first to verify the connection is working.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),

        # ── AGENT PASSPORT ───────────────────────────────────────────────────
        types.Tool(
            name="issue_agent_passport",
            description="""Issue an AgentPassport to an AI agent via the ComputeID API.

An AgentPassport gives an agent:
- A registered identity with an issuer-signed registration record (RSA-SHA256)
- A declared capability list, stored and checkable server-side
- An audit trail of logged actions
- Revocation support — verification reflects revoked status immediately

Use this whenever you spawn, create, or deploy an AI agent that will act autonomously.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "Name of the AI agent e.g. 'ResearchAgent', 'EmailAgent', 'CodeReviewAgent'"
                    },
                    "owner_org": {
                        "type": "string",
                        "description": "Organisation or company that owns this agent e.g. 'Acme Corp'"
                    },
                    "trust_level": {
                        "type": "string",
                        "enum": ["restricted", "standard", "elevated", "autonomous"],
                        "description": "Preset mapping to a capability list. restricted=[read], standard=[read, web_browse, api_call], elevated=[+code_execute], autonomous=[+spawn_agents]. You can also pass explicit capabilities instead."
                    },
                    "capabilities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Explicit capability list. Overrides trust_level if provided."
                    },
                    "model": {
                        "type": "string",
                        "description": "AI model powering the agent e.g. 'claude-sonnet-4-5', 'gpt-4', 'gemini-pro'"
                    },
                    "purpose": {
                        "type": "string",
                        "description": "What this agent is designed to do e.g. 'Research and summarise news articles'"
                    }
                },
                "required": ["agent_name", "owner_org"]
            }
        ),

        types.Tool(
            name="verify_agent_passport",
            description="Verify an agent's passport against the ComputeID API. Returns status (active/revoked), signature validity, and the declared capability list. Note: a revoked passport can still have a valid signature — check both fields.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "The passport_id (UUID) returned at issuance"
                    }
                },
                "required": ["agent_id"]
            }
        ),

        types.Tool(
            name="check_agent_capability",
            description="Check whether an agent's passport grants a specific capability. Returns granted true/false with a reason. Returns granted=false with reason 'passport_revoked' if the passport has been revoked.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "The passport_id (UUID) to check"
                    },
                    "capability": {
                        "type": "string",
                        "description": "Capability name to check e.g. 'read', 'web_browse', 'code_execute'"
                    }
                },
                "required": ["agent_id", "capability"]
            }
        ),

        types.Tool(
            name="log_agent_action",
            description="Log an action taken by an AI agent to its server-side audit trail via the ComputeID API. Call this after every significant action an agent takes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "The agent's passport_id"
                    },
                    "action": {
                        "type": "string",
                        "description": "The action taken e.g. 'web_search', 'file_read', 'api_call', 'email_sent', 'code_executed'"
                    },
                    "details": {
                        "type": "object",
                        "description": "Additional details about the action e.g. {query: 'market data', url: 'example.com'}"
                    },
                    "outcome": {
                        "type": "string",
                        "enum": ["success", "failure", "partial"],
                        "description": "Outcome of the action"
                    }
                },
                "required": ["agent_id", "action"]
            }
        ),

        types.Tool(
            name="revoke_agent_passport",
            description="Revoke an agent's passport via the ComputeID API. After revocation, verify_agent_passport returns status 'revoked' and check_agent_capability returns granted=false for all capabilities. Systems that check the API will see the revocation immediately; this does not by itself stop processes that never check.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "The passport_id to revoke"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for revocation e.g. 'Unexpected behaviour', 'Task completed', 'Security concern'"
                    }
                },
                "required": ["agent_id", "reason"]
            }
        ),

        types.Tool(
            name="list_agent_passports",
            description="List all AgentPassports registered via the ComputeID API, with status and capabilities.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status_filter": {
                        "type": "string",
                        "enum": ["all", "active", "revoked"],
                        "description": "Filter agents by status. Default: all"
                    }
                },
                "required": []
            }
        ),

        types.Tool(
            name="get_agent_audit_log",
            description="Get the server-side audit trail for a specific agent — logged actions, outcomes, and timestamps.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "The agent's passport_id"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of log entries to return. Default: 20"
                    }
                },
                "required": ["agent_id"]
            }
        ),

        # ── DEVICE PASSPORT ──────────────────────────────────────────────────
        types.Tool(
            name="register_device",
            description="Issue a DevicePassport (RSA-2048 + ML-DSA-87) for a GPU server, robot, drone or other device. Active immediately.",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_name": {
                        "type": "string",
                        "description": "Name of the device e.g. 'NVIDIA H100 Node 1', 'GPU Cluster A'"
                    },
                    "device_category": {
                        "type": "string",
                        "description": "Free-text category e.g. 'gpu-server', 'edge-device', 'robot', 'drone', 'vehicle' (default 'generic')"
                    },
                    "organization": {
                        "type": "string",
                        "description": "Organisation that owns the device"
                    }
                },
                "required": ["device_name"]
            }
        ),

        types.Tool(
            name="list_devices",
            description="List your account's DevicePassports and their status.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),

        types.Tool(
            name="revoke_device",
            description="Revoke a device's DevicePassport.",
            inputSchema={
                "type": "object",
                "properties": {
                    "passport_id": {
                        "type": "string",
                        "description": "DevicePassport ID (from register_device or list_devices)"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for revocation"
                    }
                },
                "required": ["passport_id"]
            }
        ),

        # ── REPORTING ────────────────────────────────────────────────────────
        types.Tool(
            name="generate_audit_summary",
            description="""Generate a summary of recorded identity and audit data from the ComputeID API: registered devices, agent passports, and audit log entries over a period.

This is a data summary to support compliance workflows (e.g. EU AI Act Article 12 record-keeping). It reports what is recorded in ComputeID — it is not a compliance certification.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "period_days": {
                        "type": "integer",
                        "description": "Number of days to include in the summary. Default: 30"
                    }
                },
                "required": []
            }
        ),

        # ── AUDIT LOGS ───────────────────────────────────────────────────────
        types.Tool(
            name="get_audit_logs",
            description="Get the organisation-wide audit logs — every audit row about your account's agent passports.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of log entries to return. Default: 20, Max: 100"
                    }
                },
                "required": []
            }
        ),
    ]


# ── TOOL HANDLERS ─────────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    try:

        # STATUS
        if name == "computeid_status":
            data = await api_get("/health")
            result = f"""ComputeID API is online

Status: {data.get('status', 'running')}
API URL: {API_URL}
Time: {data.get('time', datetime.now().isoformat())}
API key set: {'Yes' if API_KEY else 'No — set COMPUTEID_API_KEY env var'}

ComputeID MCP Server v1.1.0
compute-id.com"""

        # ISSUE AGENT PASSPORT
        elif name == "issue_agent_passport":
            trust_level = arguments.get("trust_level", "standard")
            capabilities = arguments.get("capabilities") or TRUST_LEVEL_CAPABILITIES.get(trust_level, TRUST_LEVEL_CAPABILITIES["standard"])
            description_parts = []
            if arguments.get("purpose"):
                description_parts.append(arguments["purpose"])
            if arguments.get("model"):
                description_parts.append(f"Model: {arguments['model']}")
            data = await api_post("/v1/agents/register", {
                "name": arguments.get("agent_name"),
                "organization": arguments.get("owner_org"),
                "description": " | ".join(description_parts),
                "capabilities": capabilities,
            })
            if "error" in data:
                result = f"Error issuing passport: {data['error']}"
            else:
                result = f"""AgentPassport issued via ComputeID API

AGENT IDENTITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Passport ID:   {data.get('passport_id')}
Agent Name:    {data.get('name')}
Owner:         {data.get('organization')}
Status:        {str(data.get('status', '')).upper()}
Issued At:     {data.get('issued_at')}

CAPABILITIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{json.dumps(data.get('capabilities', []), indent=2)}

SIGNATURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Algorithm:     {data.get('signature_algorithm')}
Signature:     {str(data.get('signature', ''))[:64]}...
(Issuer-signed registration record. Verify any time with verify_agent_passport.)

IMPORTANT: Save the passport_id — you will need it to verify, log actions, and revoke.

To verify:        verify_agent_passport with agent_id="{data.get('passport_id')}"
To log an action: log_agent_action with agent_id="{data.get('passport_id')}"
To revoke:        revoke_agent_passport with agent_id="{data.get('passport_id')}"

compute-id.com"""

        # VERIFY AGENT PASSPORT
        elif name == "verify_agent_passport":
            agent_id = arguments.get("agent_id", "")
            data = await api_get(f"/v1/agents/{agent_id}/verify")
            if "error" in data:
                result = f"Verification failed: {data['error']}\n\nNo passport found for ID: {agent_id}"
            else:
                status = str(data.get("status", "")).upper()
                result = f"""Agent Passport Verification — ComputeID API

Passport ID:      {data.get('passport_id')}
Agent Name:       {data.get('name')}
Organisation:     {data.get('organization')}
Status:           {status}
Signature Valid:  {data.get('signature_valid')}
Algorithm:        {data.get('signature_algorithm')}
Issued At:        {data.get('issued_at')}
Revoked At:       {data.get('revoked_at') or '—'}
Capabilities:     {', '.join(data.get('capabilities', []))}

Note: signature_valid and status are independent. A revoked passport
retains a valid signature (it was legitimately issued); authorisation
decisions should require status == 'active' AND signature_valid == true."""

        # CHECK AGENT CAPABILITY
        elif name == "check_agent_capability":
            agent_id = arguments.get("agent_id", "")
            capability = arguments.get("capability", "")
            data = await api_get(f"/v1/agents/{agent_id}/capabilities/{capability}")
            if "error" in data:
                result = f"Capability check failed: {data['error']}"
            elif data.get("granted"):
                result = f"""Capability Check — GRANTED

Passport ID:  {agent_id}
Capability:   {data.get('capability')}
Scope:        {json.dumps(data.get('scope', {}))}
Bound At:     {data.get('bound_at')}"""
            else:
                result = f"""Capability Check — DENIED

Passport ID:  {agent_id}
Capability:   {capability}
Reason:       {data.get('reason', 'not_granted')}"""

        # LOG AGENT ACTION
        elif name == "log_agent_action":
            agent_id = arguments.get("agent_id")
            data = await api_post(f"/v1/agents/{agent_id}/actions", {
                "action": arguments.get("action"),
                "details": arguments.get("details", {}),
                "outcome": arguments.get("outcome", "success"),
            })
            if "error" in data:
                result = f"Error logging action: {data['error']}"
            else:
                result = f"""Action logged to ComputeID audit trail

Log ID:           {data.get('log_id')}
Agent ID:         {data.get('agent_id')}
Action:           {data.get('action')}
Outcome:          {str(data.get('outcome', '')).upper()}
Logged At:        {data.get('logged_at')}
Passport Status:  {str(data.get('passport_status', '')).upper()}
Details:          {json.dumps(data.get('details', {}))}"""

        # REVOKE AGENT PASSPORT
        elif name == "revoke_agent_passport":
            agent_id = arguments.get("agent_id")
            reason = arguments.get("reason", "No reason provided")
            data = await api_delete(f"/v1/agents/{agent_id}/revoke", {"reason": reason})
            if "error" in data:
                result = f"Error revoking passport: {data['error']}"
            else:
                result = f"""AgentPassport REVOKED via ComputeID API

Passport ID:  {data.get('passport_id')}
Status:       {str(data.get('status', '')).upper()}
Reason:       {data.get('reason')}
Revoked At:   {data.get('revoked_at')}

verify_agent_passport now returns status 'revoked' for this passport,
and check_agent_capability returns granted=false for all capabilities.
Systems that check the API will see this immediately."""

        # LIST AGENT PASSPORTS
        elif name == "list_agent_passports":
            status_filter = arguments.get("status_filter", "all")
            path = "/v1/agents" if status_filter == "all" else f"/v1/agents?status={status_filter}"
            data = await api_get(path)
            if isinstance(data, list) and len(data) > 0:
                lines = ["Agent Passports (ComputeID API)\n" + "━"*40]
                for a in data:
                    marker = "[ACTIVE] " if a.get("status") == "active" else "[REVOKED]"
                    caps = ", ".join(a.get("capabilities", []))
                    lines.append(f"{marker} {a.get('name', 'Unknown')} | {a.get('passport_id', '?')} | {caps}")
                result = "\n".join(lines)
            elif isinstance(data, dict) and "error" in data:
                result = f"Error listing passports: {data['error']}"
            else:
                result = "No agent passports found. Issue your first one with issue_agent_passport."

        # GET AGENT AUDIT LOG
        elif name == "get_agent_audit_log":
            agent_id = arguments.get("agent_id")
            limit = arguments.get("limit", 20)
            data = await api_get(f"/v1/agents/{agent_id}/actions?limit={limit}")
            if isinstance(data, list) and len(data) > 0:
                lines = [f"Audit Log for Agent {agent_id} (ComputeID API)\n" + "━"*40]
                for entry in data:
                    ts = str(entry.get("logged_at", ""))[:19]
                    lines.append(f"{ts} | {entry.get('action', '?')} | {str(entry.get('outcome', '?')).upper()}")
                result = "\n".join(lines)
            elif isinstance(data, dict) and "error" in data:
                result = f"Error fetching audit log: {data['error']}"
            else:
                result = f"No actions logged yet for agent {agent_id}. Use log_agent_action to start logging."

        # REGISTER DEVICE
        elif name == "register_device":
            body = {
                "name": arguments.get("device_name"),
                "device_category": arguments.get("device_category") or "generic",
            }
            if arguments.get("organization"):
                body["organization"] = arguments["organization"]
            data = await api_post("/v1/device-passports/register", body)
            if "error" in data:
                result = f"Error registering device: {data['error']}"
            else:
                result = f"""DevicePassport issued

Passport ID:  {data.get('passport_id')}
Name:         {data.get('name')}
Category:     {data.get('device_category')}
Organisation: {data.get('organization') or '—'}
Status:       {str(data.get('status', 'active')).upper()}
Signatures:   {data.get('signature_algorithm', 'RSA-SHA256')} + {data.get('pq_signature_algorithm', 'ML-DSA-87')}

Verify: GET /v1/device-passports/{data.get('passport_id')}/verify

compute-id.com"""

        # LIST DEVICES
        elif name == "list_devices":
            data = await api_get("/v1/device-passports")
            if isinstance(data, dict) and "error" in data:
                result = f"Error listing devices: {data['error']}"
            elif isinstance(data, list) and len(data) > 0:
                lines = ["DevicePassports (ComputeID API)\n" + "━"*40]
                for d in data:
                    lines.append(f"{d.get('passport_id', '?')} | {d.get('name', '?')} | {d.get('device_category', '?')} | {str(d.get('status', '?')).upper()}")
                result = "\n".join(lines)
            else:
                result = "No device passports yet. Use register_device to issue one."

        # REVOKE DEVICE
        elif name == "revoke_device":
            passport_id = arguments.get("passport_id")
            reason = arguments.get("reason") or "manual_revocation"
            data = await api_delete(f"/v1/device-passports/{passport_id}/revoke", {"reason": reason})
            if "error" in data:
                result = f"Error revoking device: {data['error']}"
            else:
                result = f"DevicePassport {passport_id} revoked.\n\nReason: {data.get('reason', reason)}"

        # AUDIT SUMMARY
        elif name == "generate_audit_summary":
            period_days = arguments.get("period_days", 30)
            timestamp = datetime.now().isoformat()

            device_count = 0; active_devices = 0; log_count = 0
            agent_count = 0; active_agents = 0; revoked_agents = 0
            try:
                devices = await api_get("/v1/device-passports")
                if isinstance(devices, list):
                    device_count = len(devices)
                    active_devices = len([d for d in devices if isinstance(d, dict) and d.get("status") == "active"])
            except Exception:
                pass
            try:
                logs = await api_get("/api/logs?limit=100")
                if isinstance(logs, list):
                    log_count = len(logs)
            except Exception:
                pass
            try:
                agents = await api_get("/v1/agents")
                if isinstance(agents, list):
                    agent_count = len(agents)
                    active_agents = len([a for a in agents if a.get("status") == "active"])
                    revoked_agents = len([a for a in agents if a.get("status") == "revoked"])
            except Exception:
                pass

            result = f"""COMPUTEID AUDIT DATA SUMMARY
{"="*50}
Generated:  {timestamp}
Period:     Last {period_days} days
Source:     {API_URL}

AGENT PASSPORTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total:    {agent_count}
Active:   {active_agents}
Revoked:  {revoked_agents}

DEVICES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total:    {device_count}
Active:   {active_devices}

AUDIT LOG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Entries returned (max 100): {log_count}

Identity records are issuer-signed (RSA-SHA256). Audit entries are
stored server-side with timestamps.

This is a summary of data recorded in ComputeID, intended to support
record-keeping workflows such as EU AI Act Article 12. It is not a
compliance certification or legal assessment.

compute-id.com"""

        # GET AUDIT LOGS
        elif name == "get_audit_logs":
            limit = min(arguments.get("limit", 20), 100)
            data = await api_get(f"/api/logs?limit={limit}")
            if isinstance(data, list) and len(data) > 0:
                lines = [f"Audit Logs (last {len(data)})\n" + "━"*40]
                for entry in data:
                    ts = str(entry.get("created_at", ""))[:19]
                    action = str(entry.get("action", "?")).replace("_", " ").title()
                    status = str(entry.get("status", "?")).upper()
                    lines.append(f"{ts} | {action} | {status}")
                result = "\n".join(lines)
            else:
                result = "No audit logs found yet. Logs will appear here as devices connect and agents act."

        else:
            result = f"Unknown tool: {name}"

    except Exception as e:
        result = f"Error calling {name}: {str(e)}\n\nCheck that COMPUTEID_API_URL is reachable and COMPUTEID_API_KEY is set to a valid API key."

    return [types.TextContent(type="text", text=result)]


# ── RESOURCES ─────────────────────────────────────────────────────────────────

@server.list_resources()
async def list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri="computeid://docs/quickstart",
            name="ComputeID Quick Start Guide",
            description="How to issue and verify your first AgentPassport via MCP",
            mimeType="text/markdown"
        ),
        types.Resource(
            uri="computeid://docs/trust-levels",
            name="AgentPassport Trust Levels",
            description="How trust level presets map to capability lists",
            mimeType="text/markdown"
        ),
    ]

@server.read_resource()
async def read_resource(uri: str) -> str:
    if "quickstart" in uri:
        return """# ComputeID Quick Start (MCP)

## 1. Check the connection
Use the `computeid_status` tool.

## 2. Issue an AgentPassport
Use `issue_agent_passport` with:
- agent_name: "MyAgent"
- owner_org: "My Company"
- trust_level: "standard"   (or pass an explicit capabilities list)

Save the returned passport_id.

## 3. Verify it
Use `verify_agent_passport` with the passport_id.
Authorisation decisions should require status == "active" AND signature_valid == true.

## 4. Check a capability
Use `check_agent_capability` with the passport_id and a capability name.

## 5. Log actions
Use `log_agent_action` after each significant agent action.

## 6. Revoke when done
Use `revoke_agent_passport`. Verification reflects revocation immediately.

API reference: https://api.aicomputeid.com
Full docs: compute-id.com
"""
    elif "trust-levels" in uri:
        return """# AgentPassport Trust Levels

Trust levels are convenience presets in this MCP server. They map to an
explicit capability list, which is what is stored and enforced server-side.

## restricted → [read]
Best for: sensitive data processing.

## standard → [read, web_browse, api_call]
Best for: research, summarisation, communication.

## elevated → [read, web_browse, api_call, code_execute]
Best for: engineering agents, automation.

## autonomous → [read, web_browse, api_call, code_execute, spawn_agents]
Use with caution. Best for: heavily audited agents.

You can bypass presets entirely by passing a `capabilities` array to
issue_agent_passport.

Full docs: compute-id.com
"""
    return "Resource not found"


# ── PROMPTS ───────────────────────────────────────────────────────────────────

@server.list_prompts()
async def list_prompts() -> list[types.Prompt]:
    return [
        types.Prompt(
            name="secure_agent_deployment",
            description="Best practice prompt for deploying an AI agent with identity and audit logging",
            arguments=[
                types.PromptArgument(name="agent_purpose", description="What the agent will do", required=True),
                types.PromptArgument(name="trust_level", description="Trust level needed", required=False),
            ]
        ),
        types.Prompt(
            name="audit_review",
            description="Review recorded identity and audit data for your AI infrastructure",
            arguments=[]
        ),
    ]

@server.get_prompt()
async def get_prompt(name: str, arguments: dict) -> types.GetPromptResult:
    if name == "secure_agent_deployment":
        purpose = arguments.get("agent_purpose", "general purpose")
        trust = arguments.get("trust_level", "standard")
        return types.GetPromptResult(
            description="Secure agent deployment checklist",
            messages=[types.PromptMessage(
                role="user",
                content=types.TextContent(type="text", text=f"""I need to deploy an AI agent for: {purpose}

Please help me:
1. First check ComputeID API status with computeid_status
2. Issue an AgentPassport with trust_level="{trust}" using issue_agent_passport
3. Verify the passport with verify_agent_passport and show me the result
4. Log the initial deployment action using log_agent_action
5. Show me how to revoke it if needed

Make sure the agent has appropriate capability boundaries for: {purpose}""")
            )]
        )
    elif name == "audit_review":
        return types.GetPromptResult(
            description="Audit data review",
            messages=[types.PromptMessage(
                role="user",
                content=types.TextContent(type="text", text="""Please review my ComputeID infrastructure data:

1. Check API status with computeid_status
2. List all devices with list_devices
3. List all agent passports with list_agent_passports
4. Get recent audit logs with get_audit_logs
5. Generate an audit data summary with generate_audit_summary
6. Summarise what is recorded and flag anything unusual (e.g. active agents with broad capabilities and no logged actions)""")
            )]
        )
    return types.GetPromptResult(description="", messages=[])


# ── MAIN ──────────────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream,
            server.create_initialization_options())

def run():
    """Console-script entry point (`computeid-mcp`): runs the stdio server."""
    asyncio.run(main())

if __name__ == "__main__":
    run()
