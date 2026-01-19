---
title: AI Autograder
parent: Hardware Design
nav_order: 4
has_children: true
---

# AI Autograder

As an experimental part of the course, I am playing around
with an LLM-based autograder.  If it is successful,
you will be able to upload solutions and get immediate
feedback from an advanced AI engine.

Right now, a barebones autograder is on a server is hosted on [Render](https://llmgrader-e6o7.onrender.com).
As I am building the site, it may change and go off temporarily.

## Instructions

* [How to use the autograder](./howto.md)
* [OpenAI keys and mdoels](./openai.md)
* [Submitting work on Gradescope](./submit.md)

## Submitting Your Work for Grading
For NYU students requiring to get a formal grade, do the following:

* Answer the problems that are required.  Note that in the top right, there is a display of **Optional** or **Points** for each problem.
You can skip problems that are optional.  Note that you will be expected to be answer all problems on the midterm and final.
* Attempt the problems for as many times as you like until you get correct on them.
* Once you are satisfied, follow the instructions above to **Save Results**.  The saving will produce a JSON file. Submit that JSON file in Gradescope.

In Gradescope, we will run an auto-grader will upload the results.

You may feel that you have a correct solution, but the AI may disagree.  No worries.  The AI can make mistakes.  After you upload your solution JSON, submit
a regrade request on Gradescope, and I will correct manually.

## Using a Latex File

Instead of manually typing in the solution to each question,
you can load them from a latex file. 
Download the problem Latex file from the github page.  The file,
such as `basic_logic_prob.tex` will be of the form:


```latex
\beign{enumerate}

\item \qtag{tag1} Question 1 text  

\begin{solution}  Enter your solution here
\end{solution}

\item \qtag{tag1} Question 2 text
\begin{solution}  Enter your solution here
\end{solution}
...

\end{enumerate}
```

Fill in the solutions and do change any of the other text inside the enumerate
-- the fields such as `\qtag{}` are needed for the parsing.  Once you are done with the
file, simply choose the file in the **Latex solution** dialog box and select **Load**.
Loading the solutions will populate solutions to all the questions and clear the 
grading responses for that unit.






