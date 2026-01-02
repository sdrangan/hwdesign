---
title: Building the FPGA bitstream and PYNQ Overlay
parent: Bus Basics and Memory‑Mapped Interfaces
nav_order: 5
has_children: false
---
# Creating the FPGA Bitstream and PYNQ Overlay

## Creating the FPGA Bitstream in Vivado

We are now ready to create the bitstream to program the FPGA with the design.

* Generate output products:
   - In the **Block Design** window, open the **Sources** panel (left).
   - Right-click `design_1.bd` and select **Generate Output Products...**.
   - This step converts the Block Design (BD) into HDL netlists, making it usable for synthesis.
* Create HDL wrapper:
   - The first time you generate output products, you need to generate the BD in a top-level module that Vivado can synthesize.  You only need to do this once.  If you later make chnages, you do not need to re-run this step.
   - Right-click `design_1.bd` again and select **Create HDL Wrapper...** .
   - Choose **Let Vivado manage wrapper and auto-update** (recommended).
* Run Synthesis
   - In the **Flow Navigator** panel (left), click **Run Synthesis**.
   - This converts your HDL design into a *netlist*—a set of logic elements and their interconnections.
   - You’ll see a pinwheel and the message *Running synthesis...* in the top right.
   - For simple designs, this finishes in under a minute. For larger ones, synthesis (and later steps) can take hours—so enjoy the speed while it lasts!
* Run Implementation:
   - Still in the **Flow Navigator**, click **Run Implementation**.
   - This step physically maps the synthesized logic onto the FPGA fabric.
   - Expect a few minutes of processing time.
* Generate Bitstream
   - Finally, click **Generate Bitstream** in the `Flow Navigator`.
   - This creates the `.bit` file that programs the FPGA with your design.


## Creating the PYNQ files via a script

A **PYNQ overlay** is a packaged hardware design (bitstream + metadata) that can be loaded and controlled from Python on a PYNQ-enabled board (like ZCU111, ZCU104 or RFSoC). It abstracts the FPGA logic into a Python-friendly interface.  You can either create the overlay files manually or with a script. 
The **generate bitstream** command above creates the files that we need for the overlay.  Before continuing, it is useful to bring them to a single location.
To this end, I created a script to this (actually, I got ChatGPT to write the script :) ) to perform this file collection:

* Go to the project folder.  So, for the scalar adder project this is `/hwdesign/scaler_fun`
* Activate the virtual environment for the `xilinxutils` package, if has not been activated.
* Navigate to the Vivado project directory for the board.  For example `/hwdesign/scalar_fun/scalar_fun_pynqz2/`
* In the project directory simply run:
~~~bash
   collect_overlay
~~~
This should find all the files you need and place them in the overlay directory.
* You can deactivate the virtual environment if needed.


## Creating a PYNQ Overlay files manually

 
Instead of using the script, you can also collect the files yourself manually.  I document these steps simply to explain how I wrote the script.  But, you can skip this step if the automated script in the previous part worked.

* Locate your bitstream and metadata file.  Vivado can place the files in crazy locations.  So, I suggest you go to the top directory and run the following command from the Vivado project directory for this demo.
In Linux:
~~~bash
    find . -name *.bit
    find . -name *.hwh
~~~
Or, if you are using Windows powershell:
~~~powershell
   Get-ChildItem -Recurse -Filter *.bit
   Get-ChildItem -Recurse -Filter *.hwh
~~~
You will locate files with names like:
    *  `scalar_fun_wrapper.bit` — the FPGA configuration file
    * `scalar_fun.hwh` — the hardware handoff file with IP metadata
They are generally in two different directories.  
*  In the same directory as the `.bit` file, find the TCL file, like `scalar_fun_wrapper.tcl`. This file is useful for scripting.  For some reason, there may be multiple `tcl` files in the Vivado project directory.  Take the one in the same directory as the `.bit` file.
* Copy all the files to the `overlay` directory and rename them as:  `scalar_fun.bit`, `scalar_fun.hwh`, `scalar_fun.tcl`.


---

Go to [Accessing the IP from PYNQ](./pynq.md)
