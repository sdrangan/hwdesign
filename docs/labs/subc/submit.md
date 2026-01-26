---
title: Submitting the Lab
parent: Conditional Subtraction Division
nav_order: 4
has_children: true
---

# Submitting the Lab

For NYU students that want to receive credit for the lab,
if you are running the Vitis and Vivado on your local machine, 
run the python command:

```bash
python submit.py
```

This program will look at the test vectors and validate that the tests have passed.
The program will create a zip file `results.zip` with:

- `results.json`:  A JSON file with the test results
- `subc_divide.py`:  Your python implementation
- `subc_divide.sv`:  Your SV implementation
- `test_results/tv_python.csv` and `test_results/tv_sv.csv`:  The test vector files.

Submit this zip folder on Gradescope on the lab assignment.  A Gradescope autograder will upload the grade. 

If you are running Vitis and Vivado on the [NYU machine](../../support/amd/nyu_remote.md),
you will not be able to run `python submit.py` since the python installation on that machine
is ancient and doesn't even the package `pandas`.  So, I suggest you copy the files above
to your local machine and run the `python submit.py` command there.

