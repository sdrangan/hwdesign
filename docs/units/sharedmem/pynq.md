---
title: Accessing the IP from PYNQ
parent: Shared Memory PS Interface
nav_order: 4
has_children: false
---

# Accessing the Vitis IP from PYNQ
We are now ready to access the Vitis IP from a jupyter notebook.


First connect to the RFSoC similar to the [scalar adder demo](/docs/scalar_fun/pynq.md)
and open a jupyter lab in the browser window of the host PC.


## Running the jupyter notebook
* In the file panel of jupyter lab, you can open the notebook at `/hwdesign/vector_mult/notebooks/vector_mult.ipynb`.
* The notebook is also at the [github page](https://github.com/sdrangan/hwdesign/tree/main/vector_mult/notebooks/vec_mult.ipynb)

**NOTE**:  Right now, this demo does not work.  PYNQ sees the overlay but when reading the results from memory, it is always zero.  Not sure how to fix this.
