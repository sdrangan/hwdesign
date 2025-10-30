---
title: Creating the Vitis IP
parent: Getting started
nav_order: 2
has_children: false
---

# Creating the Vitis IP
We next create a Vitis HLS project, design and build the Vitis IP for our scalar adder,
and export the IP so that we can use it in Vivado. 

## Creating the Vitis HLS Project

* Launch Vitis (see the [installation instructions]({{ site.baseurl }}/docs/installation.md#launching-vitis))
* Select `Open Workspace`.  Go to the directory `fpgademos\scalar_adder`.  This is where we will put the workspace.  `Vitis_HLS` will reopen.
* Select `Create component->Create empty HLS component`.  You will walk through the following six steps:
    * For `Name and location`, select component name as `scalar_add_vitis`
    * Set the `Configuration file` select `Empty File` which is the default
    * In `Source Files`, select top function to `add`
    * In the `Hardware` tab, you will need to select the hardware you are targetting.  Select `Part`.  Then for family, select `zynquplusRFSoC`.  You can use the part numbers to select the remaining options.  In my case, the packages is `ffvg1517`.  The speed grade is `-2` and the Temp grade is `E`.  You should see your part.
    * In the `Settings` tab, I kept all defaults, but later will change the clock speed
* Now you should have an empty project.
* Sometimes the part number was not correct.  To verify the selection of the part, on the `Flow` panel (left sidebar), go to the `C Synthesis` section and select the settings (gear box).
    * In the `General` tab, there is `part` number.  Set the part number to `xczu48dr-ffvg1517-2-e` or whatever the correct part number is 

## Creating the Vitis IP and Testbench Source files
* In the directory `scalar_add_vitis/src/`, create the source C file, `scalar_add.cpp` describing the functionality for our "IP":
~~~c
    void add(int a, int b, int& c) {
        #pragma HLS INTERFACE s_axilite port=a
        #pragma HLS INTERFACE s_axilite port=b
        #pragma HLS INTERFACE s_axilite port=c
        #pragma HLS INTERFACE s_axilite port=return
        c = a + b;
        }
~~~
This file is already in the git repo, so you can skip this step if you are using the repo.
* In the SCALAR_ADD_VITIS explorer pane (left sidebar), right click `Sources` and select `Add Source File` and open `scalar_add.cpp`.   We have now added the file to our project.
Alternatively, you could have selected `New Source File` and created the file here.
* Next create a testbench. Generally, we place the testbenches in a separate directory, which in our case will be: `scalar_add_vitis/testbench`.   Tehe must follow the same name as the component with `tb_` as a prefix.  So, for this case the file will be  `tb_scalar_add.cpp` and located in the `scalar_add_vitis/testbench` directory:
~~~c
    #include <iostream>
    void add(int a, int b, int& c);

    int main() {
      int result;
      add(7, 5, result);
      std::cout << "Result: " << result << std::endl;
      return 0;
    }
~~~

## Synthesizing and Building the Vitis IP
* In the `FLOW` panel (left sidebar), select `C Simulation->Run`.  It should run with a result of 12
* Still in the `FLOW` panel,  select `C synthesis->Run` 
* Next in the `FLOW` panel, `Package->Run`.
* The packaging will have created a directory of files containing the *IP* for the adder.  It will be located in `scalar_adder_vitis/scalar_add/add/hls/impl/ip`. 
* Note that we do not need to run the `Implementation` step -- this is for creating standalone bitstreams, not ones that will be integrated into a larger FPGA project.

---
Go to [Adding the Vitis IP](./add_ip.md)