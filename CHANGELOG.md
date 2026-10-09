# Changelog

## 2.0.0 (unreleased)

The first release that starts as installed and authenticates against the live ComputeID API. 1.2.0 was never published, so its changes are part of this release.

### Breaking
- **API-key auth.** The server sends `X-API-Key` from `COMPUTEID_API_KEY`.
  - 1.x sent `Authorization: Bearer $COMPUTEID_TOKEN`, which the API ignores, so every authenticated tool returned 401.
  - `COMPUTEID_TOKEN` is still read as a fallback, but it must hold an API key.
- **Device tools use `/v1/device-passports`** (RSA-2048 + ML-DSA-87, account-scoped). 1.x called `/api/devices`, which does not exist.
  - `register_device` takes `device_name`, `device_category`, `organization`.
  - `revoke_device` takes `passport_id`, `reason`.
  - `approve_device` is removed: device passports are active when issued.
- **Code moved into the `computeid_mcp` package.** 1.x installed a generic top-level module named `server`.

### Fixed
- **The `computeid-mcp` command now runs the server.** In 1.x the entry point pointed at an `async` function: the command exited at once with `<coroutine object main …>` and never served.
- **`python -m computeid_mcp` works.** This is the README's Claude Desktop config; in 1.x the module did not exist.
- **`mcp` is pinned to `<2`.** A fresh 1.x install pulled `mcp` 2.x, whose API this server doesn't use, and crashed on import.
- **License metadata** is Apache-2.0, matching `LICENSE` (1.x metadata said MIT).
- **Project URLs** point at this repository.
- **Docs:** the tool table matches the real tools (1.x listed a non-existent `generate_compliance_report`).

### Packaging
- Built from `pyproject.toml` (replaces `setup.py`).
- Published from GitHub Actions with PyPI trusted publishing (no stored token).

## 1.1.0
Last release before 2.0.0 (on PyPI).
