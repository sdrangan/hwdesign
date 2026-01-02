---
title: C Simulation and Synthesis 
parent: Bus Basics and Memory‑Mapped Interfaces
nav_order: 2
has_children: false
---

# Simulating and Synthesizing the Vitis IP


## C Simulation

After we have written the HLS description of the IP, our first task it to simualte the IP to ensure **functional correctness**.


* In the **FLOW** panel (left sidebar), select **C Simulation → Run**.   
    * A long simulation will begin.  
    * You will see a large number of outputs.  Within that stream of outputs, you will It should run with a result of 35 and show `Test passed!`. If you see this output, it has worked.
* Later, we will design automated scripts to parse these outputs and compare results against test vectors.  But, this simple test is sufficient for our initial example.

## C Synthesis

Following simulation, we can **synthesize** our design, which means we convert the C/C++ functions into synthesizable RTL (Verilog/VHDL), targeting the specified FPGA part.

Still in the **FLOW** panel, select **C Synthesis → Run**.  

You do not have to, but you can see the automatically generated verilog files in
~~~bash
   scalar_fun/scalar_fun_vitis/hls_component/simp_fun/hls/syn/verilog
~~~

---
Go to [Running an RTL simulation](./rtlsim.md)
