# Vitis HLS script for the stereo lab.
#
# One stage per invocation, named by the STEREO_STAGE environment variable:
#
#   base_csim    compile tb_stereo.cpp against stereo_base.cpp and run it
#   base_csynth  synthesize stereo_base.cpp
#   csim         compile tb_stereo.cpp against stereo.cpp and run it
#   csynth       synthesize stereo.cpp
#   cosim        re-run the testbench against stereo.cpp's synthesized RTL,
#                recording the ports for the timing diagram
#
# The two kernels define the same function, stereo(), so each is a project of
# its own: base_proj for stereo_base.cpp, stereo_proj for stereo.cpp.  The
# csim stage of each is the one that resets its project; the later stages
# re-open what it built.
#
# stereo_build.py runs these for you, one at a time.  You can also run a stage
# by hand, from this directory:
#
#   STEREO_STAGE=csim vitis-run --mode hls --tcl run.tcl           (bash)
#   $env:STEREO_STAGE="csim"; vitis-run --mode hls --tcl run.tcl   (PowerShell)

proc env_or {name default} {
    if {[info exists ::env($name)]} {
        return $::env($name)
    }
    return $default
}

set stage      [env_or STEREO_STAGE         "csim"]
set clk_period [env_or STEREO_CLK_PERIOD_NS 10]
# The FPGA on the Pynq-Z2 board.  Nothing in this lab is deployed, but
# synthesis needs a part to target.
set part       [env_or STEREO_PART          "xc7z020clg400-1"]

switch -- $stage {
    base_csim - base_csynth { set proj base_proj;   set src stereo_base.cpp }
    csim - csynth - cosim   { set proj stereo_proj; set src stereo.cpp }
    default {
        puts "STEREO_ERROR: unknown stage '$stage' (expected base_csim, base_csynth, csim, csynth or cosim)."
        exit 1
    }
}
set fresh [expr {$stage eq "base_csim" || $stage eq "csim"}]

if {$fresh} {
    open_project -reset $proj
} else {
    open_project $proj
}
set_top stereo
add_files $src
add_files -tb tb_stereo.cpp

if {$fresh} {
    open_solution -reset -flow_target vivado "solution1"
} else {
    open_solution "solution1"
}
set_part $part
create_clock -period $clk_period

# The testbench's one argument names the file it writes: vectors/disp_<tag>.txt.
switch -- $stage {
    base_csim {
        if {[catch {csim_design -argv "base_csim"} res]} {
            puts "STEREO_ERROR: C simulation of stereo_base.cpp failed."
            puts $res
            exit 1
        }
    }
    csim {
        if {[catch {csim_design -argv "csim"} res]} {
            puts "STEREO_ERROR: C simulation of stereo.cpp failed."
            puts $res
            exit 1
        }
    }
    base_csynth - csynth {
        if {[catch {csynth_design} res]} {
            puts "STEREO_ERROR: C synthesis of $src failed."
            puts $res
            exit 1
        }
    }
    cosim {
        if {[catch {cosim_design -argv "cosim" -trace_level port} res]} {
            puts "STEREO_ERROR: RTL co-simulation failed."
            puts $res
            exit 1
        }
    }
}

puts "STEREO_SUCCESS: stage '$stage' completed."
exit 0
