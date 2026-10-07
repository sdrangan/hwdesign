---
title: Course MCP (studying)
parent: AI Tools
nav_order: 1
has_children: false
---

# Study with Your Own AI: the Course MCP

Connect your AI assistant to the course, and it can look up the course material
for itself -- this course's actual problems and slides, not what it happens to
remember about the topic. Try asking:

- *List the problems in unit 2.*
- *Help me with the problem on the bouncing ball. Give me a hint, not the answer.*
- *Give me a problem similar to problem 4 in unit 3, then check my answer.*
- *Where are AXI4-Lite read transactions described in the class slides? Give me
  the link to the key slide.*

## What your assistant can see

- every unit's **problems**, with their figures;
- the **rubric** the [AI Autograder](../aiautograder/) grades each problem
  against, including the common mistakes it looks for;
- the instructor's **worked solutions**;
- the **lecture slides**: their text, the instructor's speaker notes, and an
  image of every slide.

It is set up to help you study: it usually starts with a hint and shows the
full solution only if you ask. Nothing you do through it is graded or recorded,
and it never sees your account, your chats or your grades.

## The address

```
https://llmgrader-e6o7.onrender.com/mcp
```

That is all you need. To check it, open it in your browser: you should see
*"This is the course MCP server, and it is running."*

## Connect Claude (claude.ai, desktop and mobile)

1. Sign in at [claude.ai](https://claude.ai) and open **Settings → Connectors**.
2. Click **Add custom connector**.
3. Name it `Hardware Design course` and paste the address above.
4. Under **Authentication**, leave **No sign-in** selected, and leave **Request
   headers** empty.
5. Click **Add**.

Claude warns that *"anyone with the server URL can use this connector."* That is
expected and safe: the course MCP only hands out course material.

The connector then appears in the Claude desktop and mobile apps too. In a
chat, make sure it is switched on in the tools menu under the message box.
Claude's free plan allows one custom connector.

## Connect VS Code (GitHub Copilot)

1. Open the Command Palette (`Ctrl+Shift+P`, or `Cmd+Shift+P` on a Mac) and run
   **MCP: Add Server...**.
2. Choose **HTTP**, paste the address, and name it `hwdesign`.
3. In Copilot Chat, switch to **Agent** mode and check the server's tools are
   ticked in the tools picker.

## Connect Claude Code

```bash
claude mcp add --transport http hwdesign https://llmgrader-e6o7.onrender.com/mcp
```

## Check that it works

In a **new** chat, ask *"List the problems in unit 2."* The assistant should
show a tool call (Claude shows a small `list_questions` box) and answer with the
unit's actual problems. If it answers from general knowledge instead, check the
connector is switched on for that chat and the address is exact.

## Tips

- **Seeing a slide.** Your assistant sees slide images but cannot paste them
  into the chat. Ask for **"the link to that slide"** and open it.
- **It can be slow.** A question that needs several lookups -- a problem, then
  the slides that cover it -- can take 20 to 30 seconds.
- **Hints first.** "Is my reasoning right?" and "give me a hint for part (b)"
  teach you more than "solve it".

The full guide, including more troubleshooting, is in the
[LLM Grader student documentation](https://sdrangan.github.io/llmgrader/docs/student/mcp.html).
