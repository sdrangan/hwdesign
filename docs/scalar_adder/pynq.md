---
title: Accessing the IP from PYNQ
parent: Getting started
nav_order: 5
has_children: false
---

# Accessing the Vitis IP from PYNQ
We are now ready to access the Vitis IP from a jupyter notebook.


## Connecting to the RFSoC

* Now follow the instructions on the [RFSoC-PYNQ getting started page](https://www.rfsoc-pynq.io/rfsoc_4x2_getting_started.html).
* The RFSoC itself has a lightweight processor, an ARM core, as part of the *processing system (PS)*.  The ARM core has been installed with a version of Linux, called petalinux, often used in embedded platforms.  Among other linux applications, the ARM core can serve as a jupyter notebook client.  You should be able to connect to the jupyter notebook client from a browser from the host PC at `http://192.168.3.1/lab`. 
* Enter the password `xilinx`.  You are now accessing the ARM core on the PS.


## Downloading the git repo on the PYNQ platform
* In the jupyter lab browser window, on the top menu `File->Terminal`.  This will open a terminal that is running on the ARM core on the FPGA board.
* Navigate to the directory:
~~~bash
cd /home/xilinx/jupyter_notebooks
~~~
This is directory we will work on the most of project.
* You can clone the git repository here, so the github repo should appear at `/fpgademos` in the file panel of the jupyter lab.
* To reload the git repository and override local changes:
~~~bash
    git fetch origin
    git reset --hard origin/main
~~~

## Running the jupyter notebook
* In the file panel of jupyter lab, you can open the notebook at `/fpgademos/scalar_adder/scalar_adder.ipynb`.
* The notebook is also at the [github page](https://github.com/sdrangan/fpgademos/tree/main/scalar_adder/notebooks/scalar_adder.ipynb)

