---
title: Installing the python package
parent: Software Set-Up
nav_order: 5
has_children: false
---

# Installing  `xilinxutils`

## Installing the package

The repository provides a python package `xilinxutils` that consists of various helper functions to work with the Xilinx tools.  Examples include
parsing of system reports or timing outputs.  You can install the package in a virtual environment as follows:


*  First, create a virtual environment.  The command below will
create an environment named `env`,
but any other environment name can be used.  I usually perform this command
in the directory just outside `hwdesign`.
~~~bash
python -m venv env
~~~
The command may take several minutes, and it may not indicate
its progress.
After completion, the virtual environment files will be in a
directory `env`.  This directory may be large.
* Activate the virtual environment:
~~~bash
.\env\Scripts\Activate.ps1  [Windows]
source env/bin/activate [MAC/Linux]
~~~
On Windows Powershell, you may get the error message
*“...Activate.ps1 is not digitally signed. The script will not execute on the system.”*
In this case, you will want to run:
~~~bash
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
~~~
   
* The first time you activate the environment, install the
package requirements:

    ~~~bash
    (env) pip install -r requirements.txt
    ~~~

*  Next, install the `xilinxutils` package as editable:

   ~~~bash
    (env) pip install -e .
    ~~~
    This step also only needs to be done once for the virtual environment.

*  You can now verify the installation with running the following in a python environment:
~~~python
    import xilinxutils
    xilinxutils.check_install()
~~~
This command should return something like:
~~~pythons
    {'package': 'xilinxutils', 
    'version': '0.1.1.dev83+ge97966f1d.d20251117', 
    'status': 'OK'}
~~~
*  You can exit the virtual environment with:
    
    ~~~bash
    (env) deactivate
    ~~~

To use the package later, you will need to activate the
virtual environment and run any commands in that environment.

## Creating a requirements file
If you update the installation in the package, you may need to re-create the
`requirements.txt` file with:

~~~bash
   python -m pip freeze > requirements.txt
~~~

If you do this on Windows, you should edit the file `requirements.txt`
as follows:

* In `requirements.txt`, you may have a line like:

~~~
pywin32==306
~~~
Delete this line since it is only needed for Windows.

* You may also find a line like:
~~~
-e git+https://github.com/sdrangan/hwdesign.git@...#egg=xilinxutils
~~~
The particular github address may be different and there may be a long version number.
This line installs the `xilinxutils` package directly from github.  But, we do not need it.
So delete this line as well.