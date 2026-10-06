---
title: Your course repository
parent: GitHub Repository
nav_order: 3
has_children: false
---

# Your course repository

Some assignments are submitted as a link to your work on GitHub. Rather than
create a new repository each time, keep all of your work for the course in
**one repository**, with a folder per assignment. You set it up once.

## Create it

1. On GitHub, create a new repository named `hwdesign-work`.
   * Make it **public**. The LLM grader reads your work through web search and
     cannot sign in to GitHub, so it cannot see a private repository.
   * Tick **Add a README file**, so the repository starts with a `main`
     branch.
2. Clone it next to your clone of the course repository:

   ```bash
   git clone https://github.com/<your-username>/hwdesign-work.git
   ```

3. Add a `.gitignore` at the top of `hwdesign-work`, so the tools' bulky
   working files stay out of the repository:

   ```
   **/prj_*/
   **/*.log
   **/.Xil/
   **/__pycache__/
   ```

   Commit and push it.

## Use it

Each assignment that uses the repository says which folder to use, for example
`cmdresp/takehome/`. Work in that folder, commit as you go, and push.

When an assignment asks for a link, give the link to **the folder**, not the
whole repository:

```
https://github.com/<your-username>/hwdesign-work/tree/main/cmdresp/takehome
```

The grader reads only that folder, so the rest of the repository can hold
your other assignments.

A few habits that make your work easy to grade, and are good practice anyway:

* **Commit small and often, with a message that says why.** "Close nsamp = 0:
  the agent had to guess" says more than "update prompt".
* **Commit what your results cite.** If a report or log is the evidence for a
  number in your write-up, commit it, even if `.gitignore` would skip it:
  `git add -f path/to/file.log`.
* **Leave out what nothing cites**: tool project directories, caches and
  scratch output.

{: .note }
> Because the repository is public, classmates can read it. Assignments that
> use it are designed so each student's work is their own: for example, each
> student chooses a different accelerator.
