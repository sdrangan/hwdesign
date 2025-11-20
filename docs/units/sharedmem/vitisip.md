---
title: Creating the Vitis IP
parent: Shared Memory PS Interface
nav_order: 1
has_children: false
---

# Creating the Vitis IP

In the previous unit on [loop optimization]({site.root}/hwdesign/loopopt), we built and optimized a simple vector multiplier IP core.  Before starting, we need to select a set of parameters and package the IP and run the Implementation.   You can build the IP manually with the Vitis GUI or via an included script.

## Building the Vitis IP with a script
* Navigate to `hwdesign/vector_mult/vmult_vitis`.
* The script is located in `scripts/build_ip.tcl`.  If you want you can change the unroll factor for the IP you want to build by modifying the line:
~~~tcl
    # Set the desired unroll factor
    set uf 4
    set sol_name "sol_uf$uf"
~~~
By default, it is set to `4`.
* Run the script:
~~~bash
vitis-run --mode hls --tcl scripts/build_ip.tcl
~~~
* Running the script will take about 1 to 2 minutes.
* The IP should be located in a directory such as `/hwdesign/vector_mult/vmult_vitis/sol_uf4/` depending on what unroll factor you used.


## Building the IP with the Vitis GUI

* Follow the instructions [loop optimization](/docs/loopopt) to build the Vitis IP project
* In `include/vmult.h` set the parameters:
~~~C
#define PIPELINE_EN 1  // Enables pipelining
#define UNROLL_FACTOR 4  // Unrolls loops when > 1
#define MAX_SIZE 1024  // Array size to test
#define DATA_FLOAT 1   // Data type:  1= float, 0=int
~~~
This will use loop unrolling.  But, you can use any parameters you like.
* In the `FLOW` panel, run the `C simulation` to make sure it works
    * You should see `Test passed!`
* Run the C synthesis:
   * Still in the `FLOW` panel, select `C synthesis->Settings` (the gear box icon). Set the clock to be `300 MHz`.
   * Run the `C synthesis`
* Next in the `FLOW` panel, run the `Package` step.  
    * Note that you do not need to run `Implementation` since we are not creating a standalone bitstream for the IP -- just a IP that can be imported into Vivado.
* The IP should be located in `/hwdesign/vector_mult/vmult_vitis/vmult_hls/`

---
Go to [Understanding AXI and Memory Transfers](./axi.md).