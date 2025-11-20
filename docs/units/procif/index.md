---
title: Basic Processor Interface
parent: Course Units
nav_order: 2
has_children: true
---

# Interfacing the IP with the Processor

In the previous unit, we built our first *accelerator* or Vitis IP.  Of coruse, the IP is useless in isolation.  In this unit, we will connect the IP to the processor.

By completing this demo, you will learn how to:


* Create a minimal **Vivado project** that integrates the IP
* Synthesize the design to generate a **bitstream**
* Build a **PYNQ overlay** that loads the bitstream onto the FPGA board and interact with the IP through Python


## Next Steps

If you want to build the IP, add it to the Vivado project, and create the overlay, start from the begining with [building the IP in Vitis HLS](./vitis_ip.md).

Alternatively, the github repo already includes a pre-built overlay file.  So, you can just skip to [accessing the Vitis IP from PYNQ](./pynq.md).



 
