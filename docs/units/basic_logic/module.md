---
title: Simple Scalar Function Module 
parent: Basic Digital Logic
nav_order: 1
has_children: false
---

# A Simple Module and Testbench

## Linear Function + ReLU

All the code for the demo is in the directory:
~~~bash
    hwdesign/demos/basic_logic
~~~
To illustrate the most simple logic, we implement a simple scalar function:
~~~python
    y = max(w*x+b, 0)
~~~
which is a linear function followed by ReLU, widely-used in machine learning.
In the directory `basic_logic`, the code is in 
`lin_relu.sv`.  This file is in **SystemVerilog**,
a so-called **Register Transfer Language** or RTL
that describes the functionality that is to occur in each clock cycle.  The code in `lin_relu.sv` is quite self-explanatory:

* The top of the module defines its inputs and outputs:
~~~systemverilog
    module lin_relu #(
        parameter WIDTH = 16
    )(
        input  logic              clk,
        input  logic              rst,   // synchronous reset
        input  logic signed [WIDTH-1:0]  w_in,
        input  logic signed [WIDTH-1:0]  b_in,
        input  logic signed [WIDTH-1:0]  x_in,
        output logic signed [WIDTH-1:0]  y_out
    );
~~~
The inputs are two operands `w_in`, `b_in`, `x_in` as well as a clock and reset.
All the values are integers with a programmable bitwidth.  When using a fixed bitwidth,
there is a possibility that the terms can overflow -- something we will discuss in
detail in later units.

* The inputs are registered on each clock cycle:
~~~systemverilog
    // Register the inputs
    always_ff @(posedge clk) begin
        if (rst) begin
            w_reg <= '0;
            b_reg <= '0;
            x_reg <= '0;
        end else begin
            w_reg <= w_in;
            b_reg <= b_in;
            x_reg <= x_in;
        end
    end
~~~

* The output is computed with a simple function like multiplication.
The output is not registered.  Instead it is the ouptut of a
**combinational path** so that it is available within the propagation delay 
from registering the inputs.
~~~systemverilog
    // Combinational output 
    always_comb begin
        u = w_reg * x_reg + b_reg;
        y_out = (u > 0) ? u : 0;
    end
~~~


## A Simple Testbench

The testbench is in `tb_lin_relu.sv` and is also a SV file.
It loops through a set of values for the inputs and feeds them to the module.
In each case, the module output is read and displayed.



---

Go to [Simulating the example](./simulation.md).