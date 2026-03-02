# ANF Foundry SelfOps

## What This Is

A production-ready GitHub accelerator demonstrating Azure AI Foundry Agents managing Azure NetApp Files infrastructure through function calling. Part of a 3-repo training suite for Microsoft internal teams (100+ attendees).

**Version**: 0.2.0 | **Tests**: 20/20 | **Tools**: 7 | **Status**: Demo-ready

## Stack

- **Language**: Python 3.11+
- **Package manager**: pip with pyproject.toml (PEP 621)
- **Linter/formatter**: ruff
- **Type checker**: mypy (strict mode)
- **Test framework**: pytest with pytest-asyncio (20 unit tests)
- **Azure SDKs**: azure-ai-projects 1.0.0 (GA), azure-ai-agents >=1.1.0 (GA), azure-mgmt-netapp >=14.0.0
- **Auth**: azure-identity (DefaultAzureCredential)
- **Resilience**: tenacity (retry with backoff), custom circuit breaker
- **Logging**: structlog (JSON/text)
- **IaC**: Bicep (VNet + NSG + ANF + Key Vault + MI + RBAC)
- **Container**: Docker with multi-stage builds
- **CI/CD**: GitHub Actions

## Project Structure

```text
src/
├── main.py              # Entry point — interactive CLI + signal handlers
├── config/              # Settings via pydantic-settings, validators, .env loading
├── anf_client/          # azure-mgmt-netapp SDK wrapper
│   ├── client.py        # ANFClient (7 methods, all with retry + circuit breaker)
│   └── models.py        # Pydantic models: VolumeInfo, SnapshotInfo, AccountInfo, etc.
├── agent/               # Foundry Agent lifecycle
│   ├── foundry_agent.py # Agent setup, thread/run loop, function call handling, 300s timeout
│   └── instructions.py  # System prompt and agent name constants
├── tools/               # Function calling layer
│   ├── definitions.py   # FunctionTool JSON schemas (7 tools)
│   └── executor.py      # Dispatch + arg validation + destructive ops gate
scripts/
├── deploy.sh            # End-to-end Bicep + Foundry CLI deployment
└── teardown.sh          # Safe resource group deletion
infra/                   # Bicep IaC (VNet, NSG, ANF, Key Vault, MI, RBAC)
tests/                   # 20 unit tests (1 test file)
docs/                    # DEPLOYMENT.md, ARCHITECTURE.md, RBAC.md
```

## Key Commands

```bash
# Install
pip install -e ".[dev]"

# Lint + format
ruff check src/ tests/ --fix
ruff format src/ tests/

# Type check
mypy src/

# Test (unit only, no Azure creds needed — 20 tests)
pytest tests/ -v -m "not integration"

# Run the agent
python -m src.main

# Deploy (one command)
bash scripts/deploy.sh <sub-id> <resource-group> <location>

# Teardown
bash scripts/teardown.sh <resource-group>

# Build container
docker build -t anf-foundry-selfops .
```

## Code Conventions

- All public functions have docstrings with Args/Returns
- Use Pydantic v2 models for all data structures crossing boundaries
- Type hints on every function signature — no `Any` unless unavoidable
- Imports: stdlib → third-party → local, separated by blank lines
- Use `from __future__ import annotations` in every module
- Error handling: catch specific exceptions, log with context, return structured OperationResult
- No print() in library code — use structlog
- Environment config via pydantic-settings, never hardcoded
- All SDK calls through `_through_circuit()` for circuit breaker protection
- All ANF client methods decorated with `@with_retry()` for transient failure resilience

## Azure SDK Patterns

- Always use `DefaultAzureCredential()` — never hardcode keys
- ANF management operations are long-running (LRO) — call `poller.result()` to wait
- The Foundry agent SDK 1.x uses threads + runs + create_and_process_run pattern
- Function calling flow: create_run → poll status → handle requires_action → submit_tool_outputs → poll again
- SDK 2.x (preview) uses PromptAgentDefinition + Responses API — see migration notes in foundry_agent.py

## Progressive Disclosure

Before working on a specific area, read the relevant doc:

- `docs/ARCHITECTURE.md` — Module map, data flow, middleware integration
- `docs/DEPLOYMENT.md` — Full deployment guide (14 sections)
- `docs/RBAC.md` — RBAC, managed identity, secret handling
- `CHANGELOG.md` — Version history
- `TODO.md` — Completed items + future roadmap
- `agent_docs/` — Research docs (architecture, SDK patterns, cloud design patterns, testing)
