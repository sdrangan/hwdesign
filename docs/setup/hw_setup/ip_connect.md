---
title: Getting IP connectivity
parent: Hardware Set-Up
nav_order: 3
has_children: false
---

# Providing IP connectivity for the FPGA board
If the FPGA board (e.g., RFSoC or PYNQ) is connected directly to the host, it may not have Internet access.
However, the board can obtain IP access through the IP access on your host machine.  
You’ll bridge your Windows Wi-Fi (or other internet-connected interface) to the Ethernet interface connected to the FPGA board. Thoe host will act as a NAT gateway.

## Setting a Windows Host

* Open **Control Panel->Network and Internet->Network Connections**
* Identify the interface associated with the FPGA board.  Typically, this is `Ethernet 2` or `Ethernet 4`.
    * You can also see which one from running the powershell command `ipconfig` and identifying the interface on the subnet.
    * For example, for the PYNQ-Z2 board, the IP address will be on the `192.168.2.xx` subnet
* Still in the **Network Connections** panel, right click on whichever interface you are using for connectivity to the Internet and select **Properties**.  
    * For example, this could be `Wi-Fi`.
* Check: ✅ "Allow other network users to connect through this computer’s Internet connection"
* In the dropdown, select the Ethernet interface connected to the PYNQ-Z2 or the FPGA board
* Click **OK**
* Windows will automatically assign a static IP (usually `192.168.137.1`) to the Ethernet interface.  You can confirm the IP address with a command like:
~~~powershell
     Get-NetIPAddress | Where-Object {$_.InterfaceAlias -like "Ethernet*"}
~~~
This will return something like:
~~~powershell
    IPAddress         : 192.168.137.1
    InterfaceIndex    : 43
    InterfaceAlias    : Ethernet 2
    AddressFamily     : IPv4
~~~
from which we can see the IP address of the Ethernet interface.  For the instructions below, we will call this address `<host_ip_addr>`
* You may lose connectivity to the FPGA board since Windows will assign it a new IP address. To find the new address, type:
~~~powershell
   arp -a
~~~
Look for IP addresses in the same subnet as the IP address of the Ethernet interface, in our example, `192.168.137.x`.
Try pinging those IPs to see which one has connectivity.  For example, it could be `192.168.137.139`
* You should now be able to reconnect the browser to the `http://192.168.137.139:9090/lab`
* For Windows host, the FPGA board should automatically acquire a gateway and DNS server.  You can test as follows:
    * Open a terminal on the FPGA board (e.g., via Jupyter lab)
    * Try `ping 8.8.8.8` meaning the gateway is set up
    * Try `ping www.google.com` meaning the DNS is working
    

## Setting Up a Linux Host

* On the Linux host machine, run
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
   * In the instructions below, we will call this interface name `pynq_if_name`.
* Get the IP address of the host machine interface to the board:
   * In the terminal of the host machine, type `ifconfig`.
   * This will list a number of interfaces.  Find the interface likely associated with connection to the board.   It will likely be on the same subnet as the interface on the PYNQ.
   * On the NYU lab machine, the IP address is `192.168.3.102`
   * Test that this is the correct IP address by trying to ping that IP address from the board.
* Open a terminal on the FPGA board (e.g., PYNQ-Z2).  You can do this from Jupyter Lab.
* On the PYNQ terminal 
~~~bash
    sudo route add default gw <host_ip_addr> <pynq_if_name>
~~~
So, in our example with the Windows host:
~~~bash
    sudo route add default gw 192.168.137.1 eth0
~~~
* Finally, you may need to add a DNS server.  you can add Google's DNS server:
~~~bash
    sudo bash -c 'echo "nameserver 8.8.8.8" > /etc/resolv.conf'
~~~
* Test `ping www.google.com` to make sure you have connectivity.
