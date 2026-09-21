# Agent Guidelines

Universal patterns and constraints for building Pro-Code AI Agents.

## Core Architecture

- All agents implement the A2A protocol
- Expose `/.well-known/agent.json` for agent discovery
- Support streaming responses

## Universal Constraints

- **NEVER call SAP APIs directly** — all SAP API consumption MUST go through MCP servers
- Never fabricate, guess, or invent data — always use tools to retrieve live data
- Relay tool errors verbatim without embellishment
- No Git operations, no authentication setup during implementation

## Business Instrumentation

ALL business logic steps MUST be instrumented:
- Pattern: `[MILESTONE_ID].[achieved|missed]: [description]`
- Add OpenTelemetry custom spans for each business step

## Testing Requirements

- Coverage must be ≥ 70%
- Mock all external systems (AI Core, MCP servers, SAP APIs)
- Tests must run offline
- One unit test per tool, one integration test for end-to-end flow
