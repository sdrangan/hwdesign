---
title: Course Units
parent: NYU class
nav_order: 1
has_children: true
---


A tentative set of units is as follows.  I've only added a few units so far, but I am hoping to get done by the end of the semester.  Problem sets can also be found on the [AI Grader portal](../aiautograder/), but this website is experimental.

* Course Introduction
    * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit00_course_intro/course_intro.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit00_course_intro/course_intro.pptx) 
    * [Software and hardware set-up](./setup/)
* Unit 1:  Basic digital logic
    * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit01_basic_logic/basic_logic.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit01_basic_logic/basic_logic.pptx) 
    * [SystemVerilog Demo:  Simple scalar functions](../demos/basic_logic/)
    * [Problems](../../units/unit01_basic_logic/prob/basic_logic.html) 
    * Lab:  [Division by conditional subtraction](../labs/subc/)
* Unit 2:  Numeric Representations
    * [Review of number systems](../../units/unit02_numbers/review_numbers.pptx) from previous class
    * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit02_numbers/numbers.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit02_numbers/numbers.pptx) 
    * [In-class exercise](../../units/unit02_numbers/numbers_inclass.ipynb)
        <a href="https://colab.research.google.com/github/sdrangan/hwdesign/blob/main/units/unit02_numbers/numbers_inclass.ipynb" target="_blank">
        <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/> 
        </a> 
    * [Problems](../../units/unit02_numbers/prob/numbers.html)
* Unit 3:  Bus basics and memory-mapped interfaces
    * Lecture:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit03_procif/procif.pdf) [[pptx]](https://github.com/sdrangan/hwdesign/tree/main/units/unit03_procif/procif.pptx) 
    * [Vitis HLS Demo:  Simple AXI4-Lite interface](../demos/procif/)
    * Problems:  [[PDF]](https://github.com/sdrangan/hwdesign/tree/main/units/unit02_procif/prob/procif_prob.pdf) [[tex]](https://github.com/sdrangan/hwdesign/tree/main/units/unit02_procif/prob/procif_prob.tex) 
* Unit 4:  FIFO and Streaming interfaces
    * [Vitis HLS Demo: AXI4-Streaming FIFO interface](../demos/fifoif/)
* Unit 5:  Timing Diagrams and Critical Path Analysis
* Unit 6:  Burst transfers and loop optimization
    * [Vitis HLS Demo: A pipelined vector multiplier](../demos/loopopt)
* Unit 7:  Shared memory and the AXI4-Memory Map protocol
* Unit 8:  Building multi-threaded control
* Unit 9:  FIR Filters
* Unit 10:  Systolic Arrays
* Unit 11:  Convolutional networks
* Unit 12:  Dataflow and message-passing architectures
* Unit 13:  Interfacing with high-speed sample 