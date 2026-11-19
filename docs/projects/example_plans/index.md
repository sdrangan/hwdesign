---
title: Example Initial Plans
parent: Project
nav_order: 5
has_children: false
---

# Example Initial Plans

Here are two example [initial plans](../planning.md). Both earn full marks from
the LLM grader, and both are kept in a GitHub repository laid out the way yours
will be, so you can also see what a plan looks like in a repo and what kind of
link to submit.

* [Conjugate gradient matrix inverse](https://github.com/sdrangan/hwdesign-work-test/blob/main/example_outlines/cg/initial_plan.md):
  the mathematics given as a Python reference model, three sub-modules, and a table of interfaces.
* [Robot arm trajectory simulation](https://github.com/sdrangan/hwdesign-work-test/blob/main/example_outlines/robotics/initial_plan.md):
  the mathematics given as equations and pseudo code, replicated sub-modules for parallelism, and a table of interfaces.

What to take from them is the level of specificity, not the topic or the
length. Each one:

* **Names the team.**
* **States the operations exactly**, in code or equations, so that two engineers
  reading the plan would build the same function.
* **Gives a reason tied to the operations** for why they suit hardware: how much
  computation there is, how much of it can run in parallel, and whether latency
  matters.
* **Breaks the design into sub-modules** and says in a sentence or two what each
  one computes.
* **Says, for every connection,** what kind of interface it is (AXI4-Stream,
  FIFO, shared memory) and what crosses it.

Your project can be in any area, and your plan can be shorter than these.
