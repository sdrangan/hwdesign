---
title: Waveflow MCP (building)
parent: AI Tools
nav_order: 2
has_children: false
---

# The Waveflow MCP: an Agent That Builds Hardware

The labs and the project are done with an **AI agent that runs on your
machine** -- one that writes code, runs Vitis, reads the results and tries
again. The Waveflow MCP server gives that agent the Waveflow reference examples
and documentation, so it builds designs the way this course does rather than
guessing.

## What you need

- **An agent that can run commands on your machine:** VS Code chat in
  **Agent** mode (recommended; a free GitHub Copilot tier exists) or Claude
  Code. A chat window in a browser is not enough, because the agent has to run
  Vitis itself.
- **Waveflow installed from a clone, in editable mode** (`pip install -e`). The
  MCP server reads the guide and the examples from the repository, which a
  plain `pip install` does not include.
- **Vitis HLS**, for anything past Python simulation -- see
  [Getting Started](../getting_started/).

## Set it up

Follow Waveflow's guide, which has the exact steps for each assistant:

**[Waveflow ▸ Installing the MCP Server](https://sdrangan.github.io/waveflow/docs/guide/ai_tooling/mcp_setup.html)**

In outline:

1. Clone Waveflow and install it in editable mode into the course's Python
   environment -- the one with `waveflow` and `hwdesign` installed.
2. Check the server can see the guide: `waveflow kb --text browse`.
3. In **your own project folder** (not the Waveflow clone), connect your agent.
   For VS Code: `waveflow_mcp_setup --workspace .`, which writes
   `.vscode/mcp.json` pointing at your environment's Python.

## Smoke test

In your project folder, ask your agent:

> Use the Waveflow MCP server to list the available frames, then describe the
> stream_inband example in three sentences.

If it answers from the MCP tools, you are ready. If it cannot see them, fix
that before you start a lab: the
[Waveflow guide](https://sdrangan.github.io/waveflow/docs/guide/ai_tooling/mcp_setup.html)
covers the usual causes.

## A word on cost

An agent building and simulating a design uses a lot of your AI plan's
allowance -- a take-home-sized accelerator took about 40 minutes with a frontier
model in testing. If your plan runs out partway through, commit what you have
and resume later.

## See also

- [Course MCP](./course_mcp.md) -- for studying the problems and slides. It
  works alongside this one.
- [Command-response mini-project](../labs/cmdresp/) -- the first lab built
  with an agent.
