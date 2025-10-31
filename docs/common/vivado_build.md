---
title: Building a Vivado Project
parent: Installation and Set-Up
nav_order: 2
has_children: false
--- 

# Building a Vivado Project

## What is Vivado?

[**Vivado**](https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/vivado.html) is Xilinx / AMD’s FPGA design suite that lets you create, simulate, and synthesize digital circuits. It provides a graphical interface to build projects, configure hardware like the Zynq processor, and generate bitstreams for deployment on supported boards.


## Creating the Vivado project with an MPSCO

An **MPSoC (Multiprocessor System-on-Chip)** is a powerful programmable device that combines multiple processing cores, programmable logic, and integrated peripherals on a single chip. In Vivado, creating a project with an MPSoC—like the Zynq UltraScale+—lets you design both software and hardware components in a unified environment.
In this note, we describe how to create a Vivado project that targets an MPSoC device. We’ll add the Processing System IP block first, which includes ARM cores and essential interfaces, and then incrementally build out the design by adding custom IP blocks and peripherals
in later demos.  To build a Vivado with an MPSOC:


* Launch Vivado (see the [installation instructions](fpgademos/docs/installation.md#launching-vivado)):
* Select the menu option `File->Project->New...`.  
   * For the project name, use `scalar_adder_vivado`.  
   * In location, use the directory `fpgademos/scalar_adder`.  The Vivado project will then be stored in `scalar_adder/scalar_adder_vivado`.
* Select `RTL project`.  
   * Leave `Do not specify sources at this time` checked.
* For `Default part`, select the `Boards` tab and then select `Zynq UltraScale+ RFSoC 4x2 Development Board`.
* The Vivado window should now open with a blank project.
* You will see a number of files including the project directory, `scalar_adder\scalar_add_vivado`.

## Getting the FPGA part number
To synthesize IP, you will need to find the  precise target part number of the FPGA that the IP will run on.  This target part number will be used for Vitis:

   * Select the menu option `Report->Report IP Status`.  This will open a panel `IP status` at the bottom.
   * In this panel, you can see the part number for something like `/zynq_ultra_ps_e_0`.  That part number will be something like `xczu48dr-ffvg1517-2-e`

