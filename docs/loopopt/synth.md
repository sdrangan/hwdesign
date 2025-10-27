---
title: Initial synthesis 
parent: Loop optimization
nav_order: 2
has_children: false
---

# Initial Synthesis

## Understanding the loop
We focus on our simple loop that, without the compiler directives (`#pragma` statements) is simply:
~~~C
for (i=0; i < n; i++) {
    c_buf[i] = a_buf[i] * b_buf[i]
}
~~~
In hardware, each iteration would be implemented as a set of steps like:
* Load `a_buf[i]` into some register, say `A`
* Load `b_buf[i]` into some register, say `B`
* Multiply `A*B` and store in some register, say `C`
* Store `C` in `c_buf[i]`
* Increment `i`

Synthesis balances trying to perform these operations
quickly vs. using a lot of hardware resources.


## Performing the initial synthesis

Let's perform an initial synthesis with no optimization
to see the results.

* In `include/vmult.h` set the parameters:
~~~C
#define PIPELINE_EN 0  // Enables pipelining
#define UNROLL_FACTOR 1  // Unrolls loops when > 1
#define MAX_SIZE 1024  // Array size to test
#define DATA_FLOAT 1   // Data type:  1= float, 0=int
~~~
which are the default parameters.  Using this configuration
is equivalent to setting the compiler directives as:
~~~C
    // Multiplication loop with optional pipelining / unrolling
    mult_loop:  for (int i = 0; i < n; i++) {
#pragma HLS pipeline off 
        c_buf[i] = a_buf[i] * b_buf[i];
    }
~~~
This setting disables pipelining, meaning that all the instructions in each iteration must complete
before the next iteration begins.
* In the `Flow` panel (left sidebar), select `C Synthesis->Run`.

The synthesis will map the C design to logic elements and build a state machine for the overall execution flow.
The synthesis for a simple design like this takes under a minute and will generate a number of files.

## Analyzing the performance
The synthesis provides an estimate of how long the loop takes to execute in hardware.  When there is no pipelining, the total
number of cycles to complete a loop is simply:
~~~
num cycles = L0*n
~~~
where `L0` is the *iteration latency* and `n` is the number of iterations.  
Thus, the total time in seconds is
~~~
T = (num cycles)*Tclk = (num cycles)/fclk
~~~
where `Tclk` is the clock period and `fclk=1/Tclk` is the clock frequency.  In this demo, we have set the clock frequency at `fclk=300 MHz`.

We can find out the parameters for our initial synthesis:

* In the `Flow` panel, select `C Synthesis->Reports->Synthesis`.  This will open a Summary Synthesis Report.  
* Scroll to the `Modules & Loop` section.
* In the table, there will be one entry for each loop.  The data for multiplication loop is `vec_mult_Pipeline_mult_loop`.

You will likely see parameters:
   * `Pipelined = no` meaning no pipelining was enabled
   * `Iteration latency = 10`, referring to the latency for each iteration, `L0`.

With the above clock rate and trip count of `n=1024`, the total latency was `10240` clock cycles or about `34.1 us`.
The reason that the number of clock cycles is so large even for multiplying two numbers is that the floating point multiplications take many clock cycles.
We'll discuss the details of floating point multiplication later, but one can imagine there are many steps including the multiplication of the mantissa and handling of the exponent.
Overall, these metrics help us understand how efficiently the loop maps to hardware — whether operations are serialized or overlapped, and how well the design meets timing constraints.
---

Go to [Loop pipelining](./pipelining.md).