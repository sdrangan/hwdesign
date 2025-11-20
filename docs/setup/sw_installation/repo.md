---
title: Cloning the Repository
parent: Software Set-Up
nav_order: 4
has_children: false
---

# Cloning the GitHub Repository

## Cloning the repoistory for a host PC
All the class material is in the [GitHub repository](https://github.com/sdrangan/hwdesign).

You can clone the repository to your host PC with the command:
~~~bash
    git clone https://github.com/sdrangan/hwdesign.git
~~~
Since I am frequently updating material, you may need to reload the repository.  If you want to pull it and override local changes:
~~~bash
    git fetch origin
    git reset --hard origin/main
~~~

## Downloading the git repo on the PYNQ platform
You can also download the repository directly on the FPGA processing system.

* After [installing the board](../hw_setup/index.md), open a jupyter lab browser window on the host PC.
* In the jupyter lab browser window, on the top menu `File->Terminal`.  This will open a terminal that is running on the ARM core on the FPGA board.
*  Then perform the `git` commands in the shell.
