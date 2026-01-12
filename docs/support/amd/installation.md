---
title: Installing Vitis and Vivado
parent: Vitis and Vivado
nav_order: 1
has_children: false
---

# Installing Vivado and Vitis 


## Selecting the version

You may not be able use the latest version of Vivado/Vitis. You must install a version that matches a valid **Board Support Package (BSP)** for your board:  At the time of writing, the current versions are:

* **RFSoC 4x2**:  Current version is 2024.1.  You can verify as follows.
   * Go to [Real Digital GitHub page](https://github.com/RealDigitalOrg/RFSoC4x2-BSP)
   * Look for files like `RFSoC4x2_2024_1.bsp` → this means you should install **Vivado/Vitis 2024.1**
* **Pynq-Z2**:  Current version is 2025.1
   * You can verify this setting when you try to [build the Vivado project](./vivado_build.md) attempt to select the board.  If the board is not an option, then you may have to 
   go to an earlier version. 

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
* In Windows, you should be able to directly double click the extractor. Follow the instructions at [Windows Installation](FPGA_intall_win.md)
* For both systems, follow the prompts:
- Select Vivado and Vitis
- When prompted for Devices, make sure to select SoC
- You may select others, but some may require additional licenses
- The installer is very large and may take several hours
- In Linux, at the end, you may be prompted to run:
~~~
    ./installLibs.sh
~~~

---

Next:  Go [launching Vitis and Vivado](./lauching.md)
