---
title: Command-Response Mini-Project
parent: Labs
nav_order: 4.5
has_children: true
---

# Unit 5 Mini-Project: A Command-Response Accelerator, Built by an AI Agent

## Overview

In this mini-project you specify a streaming accelerator, and an AI agent builds
it. Your job is the specification. The agent's job is the implementation: the
Python model, the Vitis HLS kernel, the testbench and the simulations.

That division is becoming the normal way to work. An agent can write a working
kernel in minutes, but only if it is told precisely what to build. Every detail
you leave out, the agent decides for you, and it will not always decide the way
you would have. So the skill this project teaches is **writing a specification
complete enough that someone else can build exactly what you meant**.

Every accelerator in the project follows one design pattern, the
[command-response pattern](./pattern.md): commands, configuration and data
travel on one input stream, responses and results on one output stream, and an
error stops the kernel cleanly. Read that page first.

## Learning objectives

In going through the project, you will learn how to:

* Design an accelerator around the **command-response pattern**, with
  configuration carried in-band on the stream
* Define **message formats**: command headers, response headers and data
  bursts
* Specify **error handling** that a host can rely on
* Write a **specification an AI agent can implement**, including how the result
  is to be verified
* **Read an agent's work critically**: what it built, what it had to guess, and
  whether its results back up its claims

## The four parts

| Part | Where | What you do | What you submit |
| --- | --- | --- | --- |
| 1. [Prompt design](./inclass.md#part-1-prompt-design) | In class, in pairs | Write a prompt for a simple accelerator from a short menu, and improve it with feedback from the LLM grader | The prompt text |
| 2. [Implementation to C simulation](./inclass.md#part-2-implementation-to-c-simulation) | In class | Give the prompt to an agent, which builds it through C simulation | The agent's `results.md` |
| 3. [Prompt design](./takehome.md#part-3-prompt-design) | Take-home | Write a prompt for an accelerator of your own choosing | The prompt text |
| 4. [Implementation](./takehome.md#part-4-implementation) | Take-home | The agent builds it through co-simulation and synthesis, and you iterate on the prompt | A link to the folder in your course repository |

All four parts are graded with the LLM grader, under **Command-Response
Mini-Project**. You can submit as many times as you like, so use the feedback.

## Before class

Part 2 only works in class if your setup works before you arrive. Before the
class session:

1. **An AI agent that runs on your machine and can run commands**: VS Code chat
   in Agent mode (free tier available through GitHub Copilot) or Claude Code. A
   chat window in a browser is not enough, because the agent has to run Vitis
   itself.
2. **Vitis HLS 2025.1**, installed as in [getting started](../../getting_started/).
3. **The Waveflow MCP server**, connected to your agent, following
   [Waveflow's MCP setup](https://sdrangan.github.io/waveflow/docs/guide/ai_tooling/mcp_setup.html).
   Point it at the course environment's Python, the one with `waveflow`
   installed. The MCP server is how the agent reads the Waveflow reference
   example and documentation.
4. **Your course repository**, `hwdesign-work`, created as described on
   [this page](../../support/repo/work.md).
5. **A smoke test.** In an empty folder, ask your agent: *"Use the Waveflow MCP
   server to list the available frames, then describe the stream_inband
   example in three sentences."* If it answers from the MCP tools, you are
   ready. If it cannot see them, fix that before class.

## A word on cost

An agent run uses a lot of your AI plan's allowance. In a test, the take-home
scale of accelerator took about 40 minutes with a frontier model. The in-class
accelerators are much smaller. If your plan runs out partway through, commit
what you have and resume later.

---

Next: [The command-response pattern →](./pattern.md)
