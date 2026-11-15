---
title: Course Units
parent: NYU class
nav_order: 1
has_children: true
---
# Course Units

The units for Fall 2026, in the order they are taught. Each unit has a lecture,
one or more demos you can run yourself, and problems on the
[AI Grader portal](../ai_tools/autograder.md), where you can submit them for
feedback. Most units also have a [lab](../labs/), built and graded on your own
machine and submitted to Gradescope. Units 9 and 10 are still being revised.

* Course Introduction
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit00_course_intro/course_intro.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit00_course_intro/course_intro.pptx)
  * [Software and hardware set-up](../support/)
* Unit 1:  Data Types and Combinational Logic
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit01_basic_logic/basic_logic.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit01_basic_logic/basic_logic.pptx)
  * [Review of number systems](https://github.com/sdrangan/hwdesign/tree/main/units/unit01_basic_logic/review_numbers.pdf), from a previous class
  * Demo:  [Integers, overflow and bit packing in SystemVerilog](../demos/datatypes/)
  * Lab:  [Pseudo-random number generator](../labs/prng/)
* Unit 2:  Sequential Logic and Finite State Machines
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit02_fsm/fsm.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit02_fsm/fsm.pptx)
  * Demo:  [Simple scalar functions in SystemVerilog](../demos/simp_fun/)
  * Lab:  [Division by conditional subtraction](../labs/subc/)
* Unit 3:  Floating and Fixed-Point Arithmetic
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit03_fixp/fixp.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit03_fixp/fixp.pptx)
  * [In-class exercise](https://github.com/sdrangan/hwdesign/tree/main/units/unit03_fixp/fixp_inclass.ipynb)
  * Demo:  [Fixed-point design in SystemVerilog](../demos/fixp/)
  * Lab:  [Fixed-point implementation of a cubic](../labs/cubic/)
* Unit 4:  Bus Basics and Memory-Mapped Interfaces
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit04_procif/procif.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit04_procif/procif.pptx)
  * Demo:  [A simple AXI4-Lite interface in Vitis HLS](../demos/procif/)
  * Lab:  [A root-solving accelerator in Vitis HLS](../labs/rootsolve/)
* Unit 5:  FIFOs and Streaming Interfaces
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit05_fifo/fifo.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit05_fifo/fifo.pptx)
  * Demo:  [A streaming filter with AXI4-Stream](../demos/stream/)
  * Demo:  [A command-response polynomial IP](../demos/fifoif/)
  * Mini-project:  [Command-response accelerator](../labs/cmdresp/), built with an AI agent
* Unit 6:  Timing and Critical Paths
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit06_timing/timing.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit06_timing/timing.pptx)
  * Demo:  [Timing and the clock](../demos/timing/)
  * In-class exercise:  [Beat the schedule](../demos/timing/synth_inclass.md)
* Unit 7:  Pipelining
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit07_loopopt/loopopt.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit07_loopopt/loopopt.pptx)
  * Demo:  [Pipelining a polynomial loop](../demos/loopopt/), part 1
  * In-class exercise:  [One read per iteration](../demos/loopopt/inclass.md)
* Unit 8:  Loop Unrolling and Memory
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit08_unroll/unroll.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit08_unroll/unroll.pptx)
  * Demo:  [Unrolling the polynomial loop](../demos/loopopt/unroll.md), and the memory bottleneck
  * Demo:  [Unrolling a sum](../demos/loopopt/reduction.md)
  * Demo:  [FIR: nested loops](../demos/fir/)
  * In-class exercise:  [Unrolling a dot product](../demos/loopopt/inclass_unroll.md)
  * Lab:  [Stereo depth](../labs/stereo/)
* Unit 9:  Load-Compute-Store and Line Buffers (in preparation)
  * Overlapping the load, compute and store phases that the stereo lab runs one after the other.
    It replaces last year's lecture on shared memory:
    [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit09_sharedmem/sharedmem.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit09_sharedmem/sharedmem.pptx)
* Unit 10:  Arrays and Matrix Multiplication (from Spring 2026, to be revised)
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit10_arrays/array.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit10_arrays/array.pptx)
* [Design project](../projects/)
