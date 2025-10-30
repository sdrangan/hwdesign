---
title: Accessing the IP from PYNQ
parent: Getting started
nav_order: 4
has_children: false
---

# Accessing the Vitis IP from PYNQ
We are now ready to access the Vitis IP from a jupyter notebook.


## Connecting to the RFSoC

* Now follow the instructions on the [RFSoC-PYNQ getting started page](https://www.rfsoc-pynq.io/rfsoc_4x2_getting_started.html).
* The RFSoC itself has a lightweight processor, an ARM core, as part of the *processing system (PS)*.  The ARM core has been installed with a version of Linux, called petalinux, often used in embedded platforms.  Among other linux applications, the ARM core can serve as a jupyter notebook client.  You should be able to connect to the jupyter notebook client from a browser from the host PC at `http://192.168.3.1/lab`. 
* Enter the password `xilinx`.  You are now accessing the ARM core on the PS.

## Getting IP connectivity to the RFSoC
If the RFSoC is connected to the host via USB, it may not have Internet access.  You have to 

* On the host machine, run
~~~bash
  ip link show
~~~
This will list your IP interfaces.
* Try to identify the Internet-facing interface.  On the machine in NYU, it is `enp0d31f6` since it is `state UP`.  Sometimes, it may be `eth0` or `wlan0`.
* Then in the terminal of the host machine run
~~~bash
    sudo sysctl -w net.ipv4.ip_forward=1
    sudo iptables -t nat -A POSTROUTING -o enp0d31f6 -j MASQUERADE
~~~
* Get the name of the interface on the PYNQ board connected to the host:
   * On the PYNQ board terminal, `ifconfig`.
   * If you are connected via USB, the interface should have a name like `usb0` with an IP address like `192.168.3.1`.
* Get the IP address of the host machine interface to the board:
   * In the terminal of the host machine, type `ifconfig`.
   * This will list a number of interfaces.  Find the interface likely associated with connection to the board.   It will likely be on the same subnet as the interface on the PYNQ.
   * On the NYU lab machine, the IP address is `192.168.3.102`
   * Test that this is the correct IP address by trying to ping that IP address from the board.
* On the PYNQ terminal 
~~~bash
    sudo route add default gw <host_ip_addr> <pynq_if_name>
~~~
So, in our example:
~~~bash
    sudo route add default gw 192.168.3.102 usb0
~~~
* Finally, you may need to add a DNS server.  you can add Google's DNS server:
~~~bash
    sudo bash -c 'echo "nameserver 8.8.8.8" > /etc/resolv.conf'
~~~
* Test `ping www.google.com` to make sure you have connectivity.


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

