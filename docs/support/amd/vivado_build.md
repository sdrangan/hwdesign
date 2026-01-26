---
title: Building a Vivado Project
parent: Vitis and Vivado
nav_order: 6
has_children: false
--- 

# Building a Vivado Project

In this note, we describe how create a skeleton Vivado project that targets a specific FPGA board.
Each board used in this class has a  **MPSoC (Multiprocessor System-on-Chip)**,
a powerful programmable device that combines multiple processing cores, programmable logic, and integrated peripherals on a single chip.
Here, we will add the MPSoC block first, which includes ARM cores and essential interfaces.
We will then add the Vitis IP later.

## Directory structure

In the [GitHub repo](https://github.com/sdrangan/hwdesign), there is one directory
for each project, such as `scalar_fun`, `vect_mult`, etc.  Within each project directory, we
sub-folders as follows:
~~~
hwdesign/ 
├── scalar_fun                
│   ├── scalar_fun_vitis     # vitis folder
│   ├── scalar_fun_rfsoc42   # Vivado project for RFSoC4x2
│   └── scalar_fun_pynqz2     # Vivado project for Pynq-Z2
└── vector_mult
│   ├── vmult_vitis
│   ├── vmult_rfsoc42
│   └── vmult_pynqz2
...
~~~    
The folders like `scalar_fun_vitis` are for the Vitis project and the folders like `scalar_fun_rfsoc42`
and `scalar_fun_pynqz2` are for the Vivado projects.  The Vivado projects are specific to the target
board so we need separate projects.


## Creating the Vivado project with an MPSOC

To create a Vivado project, say `scalar_fun_pynqz2`:

* [Launch Vivado](./lauching.md)
* Select the menu option **File->Project->New...**.  
   * For the project name, use `scalar_fun_pynz2`.  
   * In location, use the directory `hwdesign/scalar_fun`.  The Vivado project will then be stored in `scalar_fun/scalar_fun_pynqz2`.
* Select **RTL project**.  
   * Leave *Do not specify sources at this time* checked.
* For **Default part**, select the `Boards` tab and then select:
   * For the RFSoC 4x2, select `Zynq UltraScale+ RFSoC 4x2 Development Board`.
   * For the PYNQ-Z2 board, select `pynq-z2` or something similar
* The Vivado window should now open with a blank project.
* You will see a number of files including the project directory, `scalar_fun\scalar_fun_pynqz2`.

