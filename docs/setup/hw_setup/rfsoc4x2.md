---
title: Setting up the RFSoC 4x2 board
parent:  Hardware Set-Up
nav_order: 2
has_children: false
---

# Setting up the RFSoC 4x2 board

## RFSoC 4x2 Overview

The RFSoC 4x2 is a ready-to-use development platform featuring AMD’s Zynq UltraScale+ RFSoC ZU48DR. It combines high-speed analog-to-digital and digital-to-analog converters with a quad-core ARM Cortex-A53 processing system and programmable logic, making it ideal for software-defined radio, spectrum analysis, and advanced RF applications. The board includes 4 ADCs (5 GSPS), 2 DACs (9.85 GSPS), 8 GB DDR4 memory (split between PS and PL), and supports high-speed Ethernet via QSFP28. It is fully compatible with the PYNQ framework, enabling Python-based control and visualization through Jupyter notebooks.


*Image source: [Real Digital – RFSoC 4x2](https://www.realdigital.org/hardware/rfsoc-4x2)*

It is ideal for students and research projects in wireless communications and has been used by the NYU Wireless lab extensively.


## Setting up the hardware

Follow the instructions on the [RFSoC-PYNQ getting started page](https://www.rfsoc-pynq.io/rfsoc_4x2_getting_started.html).
The instructions will show how to set-up the board.

 The RFSoC itself has a lightweight processor, an ARM core, as part of the *processing system (PS)*.  The ARM core has been installed with a version of Linux, called petalinux, often used in embedded platforms.  Among other linux applications, the ARM core can serve as a jupyter notebook client.  You should be able to connect to the jupyter notebook client from a browser from the host PC at `http://192.168.3.1/lab`. 

Enter the password `xilinx`.  You are now accessing the ARM core on the PS.


## Downloading the Board Files

Next, you will have to download and install the **board files** for the RFSoC4x2.  [I need instructions here].
