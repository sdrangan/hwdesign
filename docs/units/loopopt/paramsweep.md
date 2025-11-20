---
title: Automated parameter sweeping
parent: Loop optimization
nav_order: 5
has_children: false
---

## Parameter Sweeping
In many designs, you may want to *sweep* over multiple parameters values to test out various tradeoffs.
In general, once the designs become more complicated, you will want to automate this process.

Vitis HLS provides a rich systems for automating testing
through *TCL* scripts.  As an example, the repository contains
a TCL script 
~~~bash
    hwdesign/vector_mult/vmult_vitis/scripts/sweep_unroll.tcl
~~~
that provides commands to run the multiple C synthesis runs with different loop unrolling factors.

The script can be run as follows:

* In the terminal, navigate to the directory,  `cd hwdesign/vector_mult/vmult_vitis`
* Run the script with:
~~~bash
vitis-run --mode hls --tcl scripts/sweep_unroll.tcl
~~~
* Running the script will take about 1 minute for each unroll factor.  There will be a large number of print outs.
At the end, it will create a set of directories:
~~~
   vmult_vitis
   ├── vmult_hls
   │   └── sol_uf1
   │   └── sol_uf2
   │   └── sol_uf4
   │   └── sol_uf8
~~~
Each directory has all the synthesis outputs for each unroll factor.  
* The script also copies the synthesis reports into a directory `vmult_vitis/vmult_reports` with files of the form
~~~
    vmult_vitis/vmult_reports/mult_loop_csynth_uf1.xml
    vmult_vitis/vmult_reports/mult_loop_csynth_uf2.xml
    ...
~~~
Each of these files is an XML file with the synthesis results for the multiplcation loop.  
* Go to the [jupyter notebook](https://github.com/sdrangan/hwdesign/blob/main/vector_mult/vmult_vitis/scripts/synth_analysis.ipynb) to analyze the results.


