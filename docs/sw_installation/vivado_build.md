---
title: Building a Vivado Project
parent: Software Set-Up
nav_order: 2
has_children: false
--- 

# Building a Vivado Project

After installing Vitis and Vivado, we first create a skeleton Vivado project that targets a specific FPGA board.
Each board used in this class has a  **MPSoC (Multiprocessor System-on-Chip)**,
a powerful programmable device that combines multiple processing cores, programmable logic, and integrated peripherals on a single chip.
In this note, we will add the MPSoC block first, which includes ARM cores and essential interfaces.
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
board so need separate projects.


## Creating the Vivado project with an MPSOC

To create a Vivado project, say `scalar_fun_pynqz2`:

* Launch Vivado (see the [installation instructions](./installation.md)):
* Select the menu option **File->Project->New...**.  
   * For the project name, use `scalar_fun_pynz2`.  
   * In location, use the directory `hwdesign/scalar_fun`.  The Vivado project will then be stored in `scalar_fun/scalar_fun_pynqz2`.
* Select `RTL project`.  
   * Leave `Do not specify sources at this time` checked.
* For **Default part**, select the `Boards` tab and then select:
   * For the RFSoC 4x2, select `Zynq UltraScale+ RFSoC 4x2 Development Board`.
   * For the PYNQ-Z2 board, select `pynq-z2` or something similar
* The Vivado window should now open with a blank project.
* You will see a number of files including the project directory, `scalar_fun\scalar_fun_pynqz2`.

## Getting the FPGA part number
To synthesize IP, you will need to find the  precise target part number of the FPGA that the IP will run on.  This target part number will be used for Vitis:

   * Select the menu option `Report->Report IP Status`.  This will open a panel `IP status` at the bottom.
   * In this panel, you can see the part number.  At the time of writing (these may change), the part numbers are:
      * **RFSoC 4x2**:  the part will be something like `/zynq_ultra_ps_e_0` and the corresponding FPGA part number is `xczu48dr-ffvg1517-2-e`.
      * **Pynq-Z2**: the part number is `/processing_system7_0` and the corresponding FPGA part number is `xc7z020clg400-1`.

