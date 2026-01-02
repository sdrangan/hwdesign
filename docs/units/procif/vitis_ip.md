---
title: Creating the Vitis IP
parent: Bus Basics and Memory‑Mapped Interfaces
nav_order: 1
has_children: false
---

# Creating the Vitis IP


## Scalar Function Example
Similar to the [basic logic examples](../basic_logic/), we will illustrate the IP 
with a simple scalar function of two inputs `a` and `b`.  


The files for the project are in the directory `hwdesign/demos/scalar_fun/scalar_fun_vitis`.
In the directory `scalar_fun_vitis/src/`,  there is the main source C file, `scalar_fun.cpp` describing the functionality for our "IP":
~~~c
    void simp_fun(int a, int b, int& c) {
        #pragma HLS INTERFACE s_axilite port=a
        #pragma HLS INTERFACE s_axilite port=b
        #pragma HLS INTERFACE s_axilite port=c
        #pragma HLS INTERFACE s_axilite port=return
        c = a * b;
        }
~~~

The function just multiplies two numbers.  You can change this as you like.
This file is already in the git repo, so you do not need to write it.
   
## A Simple Testbench
A **testbench** is a program that tests the IP, generally by giving it inputs and verifying the outputs
match the expected results.  In this case, the testbench is in the directory `scalar_fun_vitis/testbench/tb_scalar_fun.cpp`.  The code looks like:
~~~c
    int main() {
      int c;
      int a = 7;
      int b = 5;
      int c_exp = a*b;
      simp_fun(a, b, c);
      std::cout << "Result: " << c << std::endl;

      if (c == c_exp)
          std::cout << "Test passed!" << std::endl;
      else
          std::cout << "Test failed!" << std::endl;
          
      return 0;
  }
~~~
So, it basically gives the IP two numbers and tests the result matches.
Later, we will create more elaborate tests.


## Creating a Vitis HLS Project

To simulate this simple IP and testbench, 
follow the [instructions](../../support/amd/vitis_build.md) to create a Vitis HLS project
with the files:

* Top Function: `simp_fun`
* Design Files: Add `src/scalar_fun.cpp` 
* Testbench: Add `testbench/scalar_fun.cp`

---
Go to [Simulate and synthesize the IP](./csynth.md)