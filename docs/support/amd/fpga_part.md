---
title: Finding the FPGA part
parent: Vitis and Vivado
nav_order: 5
has_children: false
--- 


# Getting the FPGA part number

To synthesize IP, you will need the precise target part number of the FPGA that the IP will run on.  

At the time of writing, the processing system IP block names and FPGA part numbers for the two boards we target in the class are:

| **Board type** | **Processing System IP block** | **FPGA part number** |
|----------------|--------------------------------|-----------------------|
| RFSoC 4x2      | `zynq_ultra_ps_e_0`            | `xczu48dr-ffvg1517-2-e` |
| Pynq‑Z2        | `processing_system7_0`         | `xc7z020clg400-1`       |

> **Note:** These identifiers may change depending on board revisions or Vivado updates.  

To find the correct part number yourself:

1. [Create a Vivado project](./vivado_build.md) and add the appropriate processing system IP block.  
2. In the Vivado GUI, select **Report → Report IP Status**.  
3. This opens the **IP Status** panel at the bottom.  
4. In this panel, you can see both the processing system IP block name and the corresponding FPGA part number.


