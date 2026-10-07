---
title: AI Tools
parent: Hardware Design
nav_order: 6
has_children: true
---

# AI Tools

This course is designed to be done *with* AI, in three ways:

- **[AI Autograder](./autograder.md)** -- the portal that grades your problem
  sets, with feedback, as often as you like to resubmit.
- **[Course MCP](./course_mcp.md)** -- connects your own AI assistant to the
  course's problems, solutions and slides, for studying.
- **[Waveflow MCP](./waveflow_mcp.md)** -- lets an AI agent on your machine
  build and simulate hardware, for the labs and the project.

The two **MCP servers** both connect an AI assistant to the course, but they do
different jobs.

An **MCP server** (Model Context Protocol) is a set of tools an AI assistant
can call. Once connected, your assistant decides on its own when to use them:
you just ask your question.

| | [Course MCP](./course_mcp.md) | [Waveflow MCP](./waveflow_mcp.md) |
| --- | --- | --- |
| **For** | **Studying**: the course's problems, rubrics, worked solutions and lecture slides | **Building**: writing, simulating and synthesizing hardware designs |
| **Runs** | On the course portal. You add one web address to your assistant. | On your own machine, installed with `waveflow` |
| **Use it from** | claude.ai, the Claude app, VS Code, Claude Code | VS Code chat in Agent mode, or Claude Code, in your project folder |
| **Setup** | About a minute | About fifteen minutes, once |
| **You need it** | Any time you study -- especially before the midterm | For the labs and the project |

Both work with the free tiers of the assistants they support, and neither
costs the course or you anything beyond your own assistant's plan.

## Which one do I need?

- **"Help me with problem 4 in unit 3"**, **"give me a similar problem"**,
  **"where is this in the slides?"** -- the [Course MCP](./course_mcp.md).
- **"Build this accelerator and run it through C simulation"** -- the
  [Waveflow MCP](./waveflow_mcp.md), from an agent that can run commands on your
  machine.

You can connect both: an assistant uses whichever tools fit the question.

## Using AI well in this course

The assistant is there to help you learn, not to do the work for you. The
grading is still done on the [AI Autograder](./autograder.md) portal, against
the instructor's rubric, and what you can do on your own is what the exams test.
Ask for hints before answers, and ask it to check *your* reasoning.
