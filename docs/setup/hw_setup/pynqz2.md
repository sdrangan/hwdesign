---
title: Setting up the Pynq-Z2 board
parent:  Hardware Set-Up
nav_order: 1
has_children: false
---

# Setting up the PYNQ-Z2 board

## Setting up the hardware

The [**PYNQ-Z2**](https://www.amd.com/en/corporate/university-program/aup-boards/pynq-z2.html) is a low-cost, student-friendly FPGA development board built around the Xilinx Zynq-7020 SoC, which combines a dual-core ARM processor with programmable logic. It’s designed to make FPGA development more accessible by supporting Python-based workflows through the PYNQ framework, allowing students to interact with hardware using Jupyter notebooks. With built-in HDMI, audio, and Arduino/RPi headers, it’s a versatile platform for learning digital design, embedded systems, and hardware/software co-design.  It is one of the boards that I will try to support in these demos.



After you have purchased the board, you can follow this [excellent Youtube video](https://pynq.readthedocs.io/en/v2.3/getting_started/pynq_z2_setup.html) to set up the board and connect your host PC to the board.  Some items I noticed:

* On Windows 11, the network seemed to set automatically.  I did not need to manually set the address
* But, I needed the Ethernet cable.  I think there is a way to connect the board with the USB only, but I could not get that working.

## Connecting to Jupyter lab
Once you have completed the instructions, you will be able to connect to the board from your Host PC.  The Pynq-Z2 has a lightweight processor, an ARM core, as part of the *processing system (PS)*.  The ARM core has been installed with a version of Linux, called petalinux, often used in embedded platforms.  Among other linux applications, the ARM core can serve as a jupyter notebook client.  
You should be able to connect to the jupyter notebook client from a browser from the host PC at `http://192.168.2.99:9090/lab`. 

## Downloading the Board Files

Next, you will have to download and install the **board files** for the Pynq-Z2.
Board files tell Vivado how to interface with a specific development board. They include metadata about the FPGA part number, clock sources, I/O constraints, and available peripherals like LEDs, switches, HDMI, and audio. By installing board files, Vivado can automatically configure your project to match the physical layout and capabilities of the board—saving you from manually writing constraint files or guessing pin mappings


* Launch Vivado
* In Vivado, select **Tools->Vivado Store**
* Then follow the instructions for downloading the board files on this [AMD instruction page](https://docs.amd.com/r/en-US/ug994-vivado-ip-subsystems/Downloading-Board-Files-from-GitHub-Using-the-Vivado).
   * Search for `pynq-z2`
   * After selecting the `pynq-z2`, there is a download arrow above the list to **Install** the board files.


