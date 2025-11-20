---
title: Pipelining
parent: Loop optimization
nav_order: 3
has_children: false
---

# Loop Pipelining

In the previous section, we synthesized a simple loop without any optimization. Now we’ll explore two powerful techniques that can dramatically improve performance: **loop pipelining** and **loop unrolling**.

## What is pipelining?

Pipelining allows the hardware to start a new loop iteration before the previous one finishes — much like an assembly line. Instead of waiting for each multiply-store operation to complete before starting the next, pipelining overlaps them across clock cycles.  

In Vitis HLS, pipelining is enabled by adding the directive
~~~C
#pragma HLS pipeline II=1
~~~
inside the loop to be pipelined.  
Here, `II` stands for initiation interval — the number of cycles between starting consecutive iterations. An `II=1` means the loop starts a new iteration every cycle, which is ideal for throughput.

When pipelining is enabled, the number of cycles to execute a loop with `n` iterations is given by:
~~~
  num cycles = L0 + n*II
~~~
where `L0` is the *iteration latency*, which is the number of cycles for the first iteration to complete, and `II` is the *iteration interval*, which is the number of cycles for each additional iteration.  As before,  the total time in seconds is
~~~
   total latency = (num cycles)*Tclk = (num cycles)/fclk,
~~~
and we ahve set `fclk = 1/Tclk=300 Mhz`.   

## Synthesis with pipelining
To enable pipelining for the vector multiplication example, in `include/vmult.h`, set:
~~~C
#define PIPELINE_EN 1  // Enables pipelining
#define UNROLL_FACTOR 1  // Unrolls loops when > 1
#define MAX_SIZE 1024  // Array size to test
#define DATA_FLOAT 1   // Data type:  1= float, 0=int
~~~
Using this configuration is equivalent to setting the compiler directives as:
~~~C
    // Multiplication loop with optional pipelining / unrolling
    mult_loop:  for (int i = 0; i < n; i++) {
#pragma HLS pipeline II=1
        c_buf[i] = a_buf[i] * b_buf[i];
    }
~~~

In general, the number of cycles to execute a loop with `n` iterations with pipelining is given by:
~~~
  num cycles = L0 + n*II
~~~
where `L0` is the *iteration latency*, which is the number of cycles for the first iteration to complete, and `II` is the *iteration interval*, which is the number of cycles for each additional iteration.  The total time in seconds is
~~~
   total latency = (num cycles)*Tclk
~~~
where `Tclk` is the clock period.   For this design, I have somewhat aggressively set `fclk = 1/Tclk=300 Mhz`.

Then re-run synthesis and examine the loop report. You should see:
* `Pipelined = Yes` meaning pipelining was enabled
* `Interval = 1` meaning `II=1`
* `Iteration latency=10` meaning `L0=10` 

For our case with `n=1024` iterations at `fclk=300 MHz`, the loop takes `10+1(1024)=1034` cycles or about `3.44us`.  This is almost a `10x` speed up in comparison to no pipelining!

---

Go to [Loop unrolling](./unrolling.md).
