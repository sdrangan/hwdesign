---
title: AXI memory transfers
parent: Shared Memory PS Interface
nav_order: 2
has_children: false
---

# Understanding AXI and Memory Transfers

## Connecting Memory with AXI 

Before we build the Vivado project, we need to understand how the Vitis IP and processor system (PS) will connect to shared memory.  For the connections to memory, PS, and Vitis IP, we will use the [AXI (Advanced eXtensible Interface)](https://adaptivesupport.amd.com/s/article/1053914) standard --- a protocol used in FPGA and SoC designs to connect different components like processors, memory, and custom IP blocks. It defines how data is transferred between these components in a fast and flexible way.  AXI was developed originally by ARM, and is used in virtually every hardware design today.  

There are different types of AXI interfaces:
- **AXI4**: For high-performance memory-mapped transfers
- **AXI4-Lite**: For simple control/status registers
- **AXI4-Stream**: For continuous data streams (e.g., audio, video, FFT)

---

## Master and Slave Roles

In AXI, every transaction involves two roles:
- **Master**: Initiates the read or write operation
- **Slave**: Responds to the request

For example:
- The **Processing System (PS)** is a master when it reads/writes to memory.
- A custom **Vitis HLS IP** with `m_axi` ports is also a master — it initiates memory reads/writes.
- The **DDR memory** is a slave — it responds to read/write requests from either the PS or the IP.

---

## What We’re Doing in This Unit

In this unit, we explore a simple memory transfer:
- Either the **PS** or a **custom IP** acts as the **master**
- The **memory (DDR)** acts as the **slave**
- The master reads input data from memory, performs computation, and writes results back

One slight complication is that the custom IP (or any other programmable logic in the FPGA) does not directly access external DDR memory.  The DDR is connected only to the PS.  The custom IP will need to access the DDR memory through a memory controller on the PS.  

---

## Don’t Worry — Vivado Makes It Easy

Vivado’s **Block Design** environment makes it easy to:
- Instantiate IP blocks (like your custom vector multiplier)
- Connect AXI interfaces with drag-and-drop wiring
- Automatically generate address maps and interconnects

You’ll be able to build powerful hardware/software systems without writing low-level HDL — and still understand what’s happening under the hood.

---

Go to [Building the FPGA project](./fpgabuild.md).
