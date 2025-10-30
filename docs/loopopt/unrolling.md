---
title: Loop unrolling
parent: Loop optimization
nav_order: 4
has_children: false
---
# Loop Unrolling

## What is loop unrolling?
Now that we have discussed loop pipelining, we can get even more saving with *unrolling*.  
Unrolling duplicates the loop body to perform multiple iterations in parallel.  For example, an unroll factor of 4 is equivalent to a loop like:
~~~C
for (i=0; i < n; i += 4) {
    c_buf[i] = a_buf[i] * b_buf[i];
    c_buf[i+1] = a_buf[i+1] * b_buf[i+1];
    c_buf[i+2] = a_buf[i+2] * b_buf[i+2];
    c_buf[i+3] = a_buf[i+3] * b_buf[i+3];
}
~~~ 
where the four multiplies are performed simultaneously in each iteration.
This unrolling is realized in hardware by instantiating up to four physical multiply units that run in parallel.  Ideally, this parallelism will reduce the latency by a factor of 4.

In the above example, suppose `n=1024` and we unroll by a factor of 4.  We say `n=1024` is the *number of iterations* and the loop has 256 *trips* — each trip performs 4 multiplications in parallel due to unrolling.


In Vitis HLS, you do not need to manually unroll the loop.  You can simply add the pragma: 
~~~C
#pragma HLS UNROLL factor=4
~~~

## Array partitioning
Unforunately, unrolling may not get the full gain.  In addition to multiplications, each iteration must read from buffers `a_buf` and `b_buf` and store to `c_buf`.  Generally each of these buffers can only support one or two accesses per cycle.
Hence, they will be a bottleneck.  To avoid this bottleneck, we
partition the buffers into discrete blocks, each with its own addressing logic to parallelize access.
This is done with the compiler directive:
~~~C
#pragma HLS ARRAY_PARTITION variable=a_buf type=cyclic factor=4  dim=1
~~~
Note:
* The parameter `dim=1` refers to partitioning along the first dimension — the index used in `a_buf[i]`.
* We used `type=cyclic` to partion so that it puts `0,4,8,...` in the first partition, `1,5,9,...` in the second partition and so on.


## Synthesis with unrolling
To enable unrolling, say by a factor of 4:
In `include/vmult.h`, set:
~~~C
#define UNROLL_FACTOR 4
~~~
Then re-run synthesis and examine the loop report. You should see:
- `Interval = 1` meaning `II=1`
- `Trip count = 256` meaning that loop with `n=1024` iterations only required 256 *trips*.  

Thus, we reduce the timing by an additional factor of 4.  

---

Go to [Automated parameter sweeping](./paramsweep.md).





