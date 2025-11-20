---
title: Simple Scalar Accelerator
parent: Course Units
nav_order: 1
has_children: true
---

# Getting Started with a Scalar Function

In this unit, we will build our first *accelerator*, a simple function on scalars, such as multiplying two scalars.  Obviously, this function is so simple there is no reason to use an FPGA or any custom hardware to implement the function -- a generic processor will do fine.  However the process introduces the essential steps for hardware/software co-design and illustrates the key components of the process.

By completing this demo, you will learn how to:

* Design and synthesize a simple **Vitis IP** that performs a basic mathematical operation
* Creating interfaces to the Vitis IP using an **AXI-Lite interface**
* Simulate the synthesized Vitis IP and generate a **Value Change Dump** (VCD) file of the simulation outputs.
* View the VCD interface traces on a **timing diagrams** 


## Pre-Requirements
Prior to doing this demo, you will need to follow the [software set-up](../../setup/sw_installation/) for Vitis, Vivado, and Python.  

---
Go to [Building the Vitis IP](./vitis_ip.md).


