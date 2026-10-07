---
title: AI Autograder (grading)
parent: AI Tools
nav_order: 1
has_children: false
---

# The AI Autograder

The course's problem sets are graded by the **AI autograder**, an LLM-based
grading portal. You enter a solution, and within a minute or so it grades it
against the instructor's rubric -- with partial credit, and feedback on what
earned points and what did not. You can resubmit as often as you like, so use
the feedback.

## The portal for this course

**[llmgrader-e6o7.onrender.com/c/hwdesign](https://llmgrader-e6o7.onrender.com/c/hwdesign/)**

## How to use it

The portal is the open-source [LLM Grader](https://github.com/sdrangan/llmgrader),
and its student guide covers everything step by step:

- **[Answering and grading questions](https://sdrangan.github.io/llmgrader/docs/student/grade.html)**
  -- choosing a unit and question, writing a solution, reading the feedback.
- **[OpenAI keys](https://sdrangan.github.io/llmgrader/docs/student/openai.html)**
  -- the portal grades with your own OpenAI API key, which stays in your
  browser. Grading costs very little.
- **[The dashboard and submitting on Gradescope](https://sdrangan.github.io/llmgrader/docs/student/dashboard.html)**
  -- tracking your scores, and downloading the submission you upload to
  Gradescope.
- **[Project grading](https://sdrangan.github.io/llmgrader/docs/student/projects.html)**
  -- how the project plans are graded.

## For this course

- **Only the required problems are submitted for credit.** The dashboard's
  **required** column marks them. When you are happy with your results, download
  the submission from the dashboard and upload it to Gradescope.
- **Do all the problems anyway.** The midterm and final have comparable
  problems, and you will do those **without** the autograder or an AI
  assistant. Use the portal, and AI generally, to learn how to solve them.
- **Studying with your own AI assistant?** The [Course MCP](./course_mcp.md)
  lets it read the same problems, rubrics and solutions, plus the lecture
  slides.

## Source code and feedback

The autograder is fully open source -- see the
[GitHub repository](https://github.com/sdrangan/llmgrader). It is still
evolving, and I would love your feedback, positive or negative. If there are
features you would like, or errors you find, open an issue or send a pull
request.
