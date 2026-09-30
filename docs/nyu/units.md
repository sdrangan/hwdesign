---
title: Course Units
parent: NYU class
nav_order: 1
has_children: true
---
A tentative set of units is as follows.  The units are still in flux so new material will be added.   Each unit's problems are on the [AI Grader portal](../aiautograder/), where you can submit them for feedback.

* Course Introduction
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit00_course_intro/course_intro.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit00_course_intro/course_intro.pptx)
  * [Software and hardware set-up](../support/)
* Unit 1:  Data Types and Combinational Logic
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit01_basic_logic/basic_logic.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit01_basic_logic/basic_logic.pptx)
  * [Review of number systems](../../units/unit01_basic_logic/review_numbers.pptx) from previous class
  * Demo:  [Integers, overflow, and bit packing in SystemVerilog](../demos/datatypes/)
  * Lab:  [Pseudo-Random number generator](../labs/prng/)
* Unit 2:  Sequential Logic and Finite State Machines
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit02_fsm/fsm.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit02_fsm/fsm.pptx)
  * [SystemVerilog Demo:  Simple scalar functions](../demos/simp_fun/)
  * Lab:  [Division by conditional subtraction](../labs/subc/)
* Unit 3:  Floating and Fixed Point Arithmetic
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit03_fixp/fixp.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit03_fixp/fixp.pptx)
  * [In-class exercise](../../units/unit03_fixp/fixp_inclass.ipynb)
  * [SystemVerilog Demo:  Fixed point implementation](../demos/fixp/)
  * Lab:  [Fixed point implementation of a polynomial](../labs/cubic/)
* Unit 4:  Bus Basics and Memory-Mapped Interfaces
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit04_procif/procif.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit04_procif/procif.pptx)
  * [Vitis HLS Demo:  Simple AXI4-Lite interface](../demos/procif/)
  * Lab:  [Build a root solving accelerator in Vitis HLS](../labs/rootsolve/)
* Unit 5:  FIFOs and Streaming Interfaces
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit05_fifo/fifo.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit05_fifo/fifo.pptx)
  * Vitis HLS Demo:  [A streaming filter with AXI4-Stream](../demos/stream/)
  * Vitis HLS Demo:  [A command-response polynomial IP](../demos/fifoif/)
* Unit 6:  Timing and Critical Path Analysis
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit06_timing/timing.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit06_timing/timing.pptx)
* Unit 7:  Pipelining and Loop Optimization
  * This unit will be split into two units -- one on pipelining and one on unrolling an memory accesses
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit07_loopopt/loopopt.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit07_loopopt/loopopt.pptx)
  * [Vitis HLS Demo: A pipelined polynomial accelerator](../demos/loopopt)
  * Lab:  [Building a pipelined line intersection accelartor](../labs/intersect/)
* Unit 9:  Shared Memory architectures
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit09_sharedmem/sharedmem.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit09_sharedmem/sharedmem.pptx)
  * [Histogram accelerator](https://github.com/sdrangan/hwdesign/tree/main/demos/histogram)
* Unit 10:  Arrays and Matrix Multiplication
  * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit10_arrays/arrays.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit10_arrays/array.pptx)
