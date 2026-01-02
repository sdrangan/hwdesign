---
title: Bus Basics and Memory‑Mapped Interfaces
parent: Course Units
nav_order: 3
has_children: true
---

# Bus Basics and Memory‑Mapped Interfaces

In the previous unit, we built standalone hardware modules.  
To be useful, hardware must connect to other systems.

In this unit, we introduce **memory‑mapped interfaces**, focusing on a widely used, industry‑standard protocol called **AXI4‑Lite**. The hardware block we design will be referred to as the **accelerator** or **IP** (intellectual property), and it will connect to a **processing system**, typically a general‑purpose processor such as an ARM core.

While the previous unit used SystemVerilog, in this unit we will design the IP using **High‑Level Synthesis (HLS)**. With HLS, we describe the behavior of our design in a high‑level language such as C or C++, and the tool generates the RTL for us. RTL provides fine‑grained control but is time‑consuming and challenging for beginners, whereas HLS lets us focus on algorithms while the tool handles low‑level hardware details.  
We will use **Vitis HLS** from AMD, which provides built‑in support for AXI4‑Lite and other complex bus protocols.

By completing this demo, you will learn how to:

* Design, functionally simulate, and synthesize a simple **Vitis IP** that performs a basic mathematical operation  
* Create interfaces to the Vitis IP using an **AXI4‑Lite memory‑mapped interface**  
* View a **register file** for an IP
* Perform an **RTL‑level simulation** of the generated IP and produce a **Value Change Dump (VCD)** file  
* Visualize AXI4‑Lite transactions using **timing diagrams**

Additionally, if you want to deploy the IP on a real FPGA board, we will show you how to:

* Create a minimal **Vivado project** that integrates the IP  
* Synthesize the design to generate a **bitstream**  
* Build a **PYNQ overlay** that loads the bitstream onto the FPGA and allows you to interact with the IP from Python

## Pre-Requirements
Prior to doing this demo, you will need to follow the [software set-up](../../setup/sw_installation/) for Vitis, Vivado, and Python.  

---
Go to [Building the Vitis IP](./vitis_ip.md).


