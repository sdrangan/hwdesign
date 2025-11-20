---
title: Installing Vitis and Vivado
parent: Software Set-Up
nav_order: 1
has_children: false
---

# Installing Vivado and Vitis 


## Vitis and Vivado

The two key pieces of software we will use in this class.  Both are from AMD and can be downloaded together:

*  [**Vitis HLS** (High-Level Synthesis)](https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/vitis/vitis-hls.html) is a tool we will use to design the hardware accelerators of **Vitis IP** (IP = intellectual property).  We can write the specification for the IP in high-level language like  C, C++, or OpenCL, and Vitis HLS converts it automatically into optimized, lower-level **register transfer level** (RTL) specification for the hardware 
* [**Vivado**](https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/vivado.html) is Xilinx / AMD’s FPGA design suite that lets you create, simulate, and synthesize digital circuits. It provides a graphical interface to build projects, configure hardware like the Zynq processor, and generate bitstreams for deployment on supported boards.We then integrate that IP into a larger FPGA designs in Vivado.
In this class, we will integrate the Vitis IP into the larger Vivado FPGA project and deploy that onto the FPGA.

Both Vitis and Vivado have free versions that are fine for this class.  But, to access them you will need to [create and AMD account](https://login.amd.com/).
---

## Selecting the version

You **cannot use the latest version** of Vivado/Vitis. You must install a version that matches a valid **Board Support Package (BSP)** for your board:  At the time of writing, the current versions are:

* **RFSoC 4x2**:  Current version is 2024.1.  You can verify as follows.
   * Go to [Real Digital GitHub page](https://github.com/RealDigitalOrg/RFSoC4x2-BSP)
   * Look for files like `RFSoC4x2_2024_1.bsp` → this means you should install **Vivado/Vitis 2024.1**
* **Pynq-Z2**:  Current version is 2025.1. 

---

## Downloading the Installer

1. Go to the [Xilinx/AMD Downloads page](https://www.xilinx.com/support/download)
2. Select the correct version (e.g., **2024.1**) and choose the Linus or Windows installer.
3. After signing in, download a large `.bin`.  For linux the file will be something like
   `FPGAs_AdaptiveSoCs_Unified_2024.1_0522_2023_Lin64.bin`

---

## Running the Installer

* In Linux:
    * The file will be in `/home/<username>/Downloads`
    * Double-clicking won’t work
    * Open a terminal and run:
   ```bash
   chmod +x FPGAs_AdaptiveSoCs_Unified_2024.1_0522_2023_Lin64.bin
   ./FPGAs_AdaptiveSoCs_Unified_2024.1_0522_2023_Lin64.bin
   ```
   This will run the installer
* In Windows, you should be able to directly double click the extractor
* For both systems, follow the prompts:
- Select Vivado and Vitis
- When prompted for Devices, make sure to select SoC
- You may select others, but some may require additional licenses
- The installer is very large and may take several hours
- In Linux, at the end, you may be prompted to run:
~~~
    ./installLibs.sh
~~~

## Launching Vivado in Linux

Once you have installed Vivado, it can launched as follows from any terminal window:

* First`cd` to where Vivado is installed.  For the NYU machine, this is `/tools/Xilinx/Vivado/2024.1`
* Run `source settings64.sh`
* `cd` to the directory were you want to run the Vivado project.
* Run `vivado` from the command line.
* The Vivado gui should launch

## Launching Vitis in Linux

Launching Vitis follows almost the same sequence:

* First `cd` to where Vitis is installed.  For the NYU machine, this is `/tools/Xilinx/Vitis_HLS/2024.1`
* Run `source settings64.sh`
* `cd` to the directory were you want to run the Vitis project.
* Run `vitis_hls` from the command line.
* The Vitis Unified IDE gui should launch

