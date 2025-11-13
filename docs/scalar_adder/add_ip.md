---
title: Addding the Vitis IP 
parent: Getting started
nav_order: 3
has_children: false
---

# Adding the Vitis IP to the FPGA Project
We next need to add the IP to the Vivado project. 

## Locating the IP folder
After the IP has been synthesized, Vitis will create all the files for the IP in a folder with `impl/ip`.  You can locate this folder with a command like:
~~~bash
    find . -type d -path "*/impl/ip"
~~~
In the scalar adder case, this gets the directory  `./scalar_add_vitis/add/hls/impl/ip`

## Adding the Vitis IP to Vivado


* Go to **Tools->Settings->Project Settings->IP->Repository**.  Select the `+` sign in **IP Repositories**.  Navigate to the directory with the adder component.  In our case, this was at:  `fpgademos/scalar_adder/scalar_add_vitis/add/hls/impl/ip`.  
* Select the `Add IP` button (`+`) again.  Add this IP.  Now the `Add` block should show up as an option.  If it doesn't it is possible that you synthesized for the wrong FPGA part number.  
* You should see an Vitis IP block with ports `s_axi_control`, `interrupt` and some clocks.  Select the **run block automation**.  This will connect the IP to the processing system and may add some additional blocks for resetting the processor and interfacing the IP with the processor.  
* In this simple example, we will not connect the `interrupt` signal.
* Select the Vitis IP block.  In the `Block Properties` panel, select the `General` tab, and rename the block to `add`.  This is the name that we will use when calling the function from `PYNQ`.


## Updating the Vitis IP
If you re-synthesize the Vitis IP, you will need to **update** it in Vivado.  You don't
have to delete the IP and re-add it.  Just follow the following steps.

* Update the IP catalog
   - In Vivado, go to **Tools → Settings → IP → Repository**.
   - Click **Refresh All** or **Add Repository** if needed.
   - Vivado will detect the new version and update the IP catalog.
* Upgrade the IP in your block design:
   - Select the **Open block design**  in the left panel under **IP integrator**
   - You may see a warning message that the current IP is out-of-date
   - Select the IP block 
   - On the bottom you will see an option **Upgrade IP**.
* Now follow the next steps as usual to re-build the bitstream and overlay


---
Go to [Building the FPGA bitstream and Overlay](./fpga_build.md)
