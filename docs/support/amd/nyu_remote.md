---
title: Using the NYU remote server
parent: Vitis and Vivado
nav_order: 4
has_children: False
---

# Connecting to Vitis and Vivado on the NYU Server

## Connecting via SSH

If you are an NYU student enrolled in the class, NYU IT will have set up an account
on the NYU EDA servers so that you can run Vitis and Vivado remotely.
This way you do not need to install Vitis and Vivado on your local machine.

If you just want a simple terminal, you can log into the machines with any SSH client.
For example, in Windows, you can use [Mobaxterm](https://mobaxterm.mobatek.net/)
which has **ssh** and **scp**.  There is also built in `ssh` and `scp` in Powershell.
In MacOS, they are also built into the terminal app.

To connect, you need to be on the NYU network or connected via VPN.  Then, select the following
for your connection.
* **Host** select one of `ecs02.poly.edu` to `ecs06.poly.edu`
* **Username**: your netid
* **Port**: 22

For example, from the terminal or Powershell:

```bash
ssh <netid>@ecs02.poly.edu
```

## Downloading the FAST-X Client 

You can do most of all the labs and demos from the terminal only.
But, if you want a GUI, you can do the following:

* Download the [FAST-X client](https://www.starnet.com/download-fastx-client/)
    * Clients are available for Window, MacOS, and Linux
* Launch the Fast-X client
    * On Windows, you can launch it from the Start menu
* Before connecting, you must be on the NYU network (either on campus, or connected via VPN)
* In the Fast-X Window, select the **+** sign near the top left to add a connection.  Select
host, username and port as above.
* The connection option will now appear in the main window.  Double click on that.
* Enter your NYU password
* One connected there will be another **+** sign near the top left.  Select that sign and
you will be provided an option for a Gnome terminal or Default Desktop.  You can use either.

## Launching Vitis and Vivado within the Remote server

Once you are in the server, you can now activate most of the command line AMD tools with:

```bash
source tcshrc_xilinx_local
```

Run this command from your home directory.  For example, you can run:

```bash
$ which vitis_hls
$ vitis_hls -version
$ which vivado
$ vivado -version
```

One caution:  The NYU installation is 2023.1, which is a bit old.  But, so far,
everything has worked.

## Using Python

Right now, the python installation on the NYU machine is very old and has very few 
packages.  So I suggest that you run the Vitis and Vivado on the NYU server.
Then, for python post processing, copy the files from the remote machine to your local machine
and run the commands there.

Note that the first labs use the script `sv_sim`.  This is also part of a python 
package that you will not have access to on the remote machine.  To run this script, I suggest the following

* Clone the git repository to your home directory

```bash
cd ~
git clone https://github.com/sdrangan/hwdesign.git
```

* Navigate to the lab or demo you want to do.  For example, for the first lab:

```bash
cd hwdesign/labs/subc
```

* You can now run the file from `sv_sim` from any directory via:

```bash
python3 ~/hwdesign/scripts/sv_sim.py --source <sourcefiles> --tb <tbfiles>
```

    