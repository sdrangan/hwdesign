---
title: How to use it
parent: AI Autograder
nav_order: 1
has_children: false
---

# How to Use the Autograder?

On the main page, you will see the following items:

* **Unit dropdown**:  You should see a dropdown menu of the units you
in the class you can problems for.  These are the [class units](../nyu/index.md).  Right now, there is just
one unit `unit1_basic_logic`.   
* **Question dropdown**:  Once you select the unit, you should see a dropdown menu of questions.  These are the questions
in the Problem section for that unit.  The [class units page](../nyu/index.md) also 
has the questions in a PDF form.
* **Question box**:  After you select a question a text version
of the question will appear.  It is plain text,
so code blocks and equations are rendered very simply, 
and there are no figures.  But you can go the PDF on the class units
page if you want to see the full questions.
* **Your Solution box**:  Here you can type in a solution to grade.
You can write it in latex if you like, but text is OK too.
The LLM is pretty good at figuring out what you are trying to say.
* **Grade button**:  Hit the grade button and in a few tens of seconds, you should see a **Feedback** and a longer **Explanation**.  Right now, it just gives **Correct** or **Incorrect**.  I may give part marks later.


## Saving and Loading Your Work

To **save** your results, beside the Unit dropdown, you will see a button **Save Results**.  For all problems in the unit that you have attempted to grade,
clicking the button will save:
- Your solution
- The feedback from OpenAI
- The full explanation
- The grade result

This will be downloaded to a JSON file to your Download folder.  You can store anywhere.

Your answers are generally served on your browser.  But, if you want to recover them you can click the **Load Results** button and select the JSON file that you
save above.
