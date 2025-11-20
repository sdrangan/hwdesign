---
title: Building the FPGA project
parent: Shared Memory PS Interface
nav_order: 3
has_children: false
---

# Creating the Vivado project

## Creating the project with the MPSOC
We first create an Vivado project with the MPSOC:

* Launch Vivado (see the [installation instructions]({{ site.baseurl }}/docs/common/installation.md#launching-vivado)):
* Select the menu option `File->Project->New...`.  
   * For the project name, use `vmult_vivado`.  
   * In location, use the directory `hwdesign/vec_mult`.  The Vivado project will then be stored in `hwdesign/vec_mult/vmult_vivado`.
* Select `RTL project`.  
   * Leave `Do not specify sources at this time` checked.
* For `Default part`, select the `Boards` tab and then select `Zynq UltraScale+ RFSoC 4x2 Development Board`.
* The Vivado window should now open with a blank project.

## Add and configure the Zynq Processor
* In the `Block Design` window select the `Add IP (+)` button.  Add the `Zynq UltraScale+ MPSoC`.  This will add the MPSoC to the design.
* Add the Slave AXI on the PS.  Recall that this is the interface that will be used by the IP to access the DDR.
   * Double click the `Zynq UltraScale+ MPSoC` that you just added.
   * On the `Page Navigator` panel (left) select `Switch to Advanced Mode`. 
   * Select`PS-PL connection->Slave Interface->AXI HP0 FPD`.  The `FPD` stands for the *full power domain* which includes the ARM core, DDR controller, and high performance AXI ports.
   * Set the bit width to 32 since we will be using floating points.  
* Run the `Connection automation`.
* Connect the `pclk` to the `maxihpm0_fpd_aclk`, `maxihpm1_fpd_aclk`, and `saxihp0_fpd_aclk` ports.  
* Set the clock frequency for the PL to match what we synthesized the Vitis IP for.
   * Double click the `Zynq UltraScale+ MPSoC`
   * Select `Clock Configuration->Low Power Domain Clocks->PL Fabric Clocks`.  
   * Set the frequency to `PL0` or whichever clock is used to 300 MHz, or some frequency less than what you valdidated the Vitis IP for.

## Adding the Vitis IP to Vivado
* Go to `Tools->Settings->Project Settings->IP->Repository`.  Select the `+` sign in `IP Repositories`.  Navigate to the directory with the adder component.  In our case, this was at:  `hwdesign/vector_mult/vmult_vitis/vmult_hls/vec_mult/hls/impl/ip`.  
* Select the `Add IP` button (`+`) again.  Add this IP.  Now the `Vec_Mult` block should show up as an option.  If it doesn't it is possible that you synthesized for the wrong FPGA part number.  
* You should see an Vitis IP block with ports `s_axi_control`, `interrupt`, `m_axi_gmem` and some clocks.  Select the `run block automation`.
* Connect the `interrupt` on the Vitis IP to the `pl_ps_irq0` so that the PS can see the Vitis IP interrupt.
* Select the `vect_mult` block.  In the `Block Properties` panel, select the `General` tab, and rename the block to `vect_mult`.  This is the name that we will use when calling the function from `PYNQ`.
* Run the `Connection automation`. 
   *  This will connect the `m_axi_gmem` on the Vitis IP to the `S_AXI_HP0_FPD` which connects the master AXI on the IP to the DDR controller on the PS.  Importantly, it may add a `AXI Smart connect` between the port to deal with address translation.  Stupidly, Vivado lets you directly connect  `m_axi_gmem` to `S_AXI_HP0_FPD` even if they are mis-matched.

## Creating the FPGA Bitstream and PYNQ Overlay
Follow the similar steps in [Scalar adder demo](/hwdesign/scalar_fun/fpga_build) to create the bitstream and the PYNQ overlay.  If you want to skip this step, the overlay files are in `hwdesign/vector_mult/overlay/`.




