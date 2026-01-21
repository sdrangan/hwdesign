---
title: Building a Python Model
parent: Conditional Subtraction Division
nav_order: 2
has_children: false
---

# Building a Python Golden Model

Before implementing the function in SystemVerilog, it is better to
develop a model in a language like python where the debugging is simple.
This python simulation will serve
as a **golden model** meaning that it can provide a verified reference for the 
hardware design. 

To build the golden python model, complete the file `subc_divide.py`. 
Once you have written the function, you can test the function with:

```bash
python test_subc_divide.py [--ntest <ntest>]
```

This function will run the `<ntest>` tests with random values of `a`, `b`, and `nbits`. 
Each test passes if

```python
| a/b - qhat | <= 1 / (2**nbits)
```

The outputs of the results are stored in a `test_outputs/tv_python.csv`.  
The default for `ntest=100`.  You should get a result like:

```bash
Test results saved to test_outputs/tv_python.csv
Number of tests passed: 100 out of 100
```

If some test fail, you can look at the `test_outputs/tv_python.csv` to see the error and try to debug it.

----

Go to [Building a SystemVerilog module](./sv.md).





