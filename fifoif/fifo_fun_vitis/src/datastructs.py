# datastructs.py:  Generates the include files for the data structures

from xilinxutils.dsgen import DataStructGen, FieldInfo, IntType

# Stream bit widths to support
stream_bus_widths = [32, 64]

# Command structure
fields = [
    FieldInfo("trans_id", IntType(16)),
    FieldInfo("a", IntType(32)),
    FieldInfo("b", IntType(32))]
cmd_struct = DataStructGen("Cmd", fields)
cmd_struct.stream_bus_widths = stream_bus_widths
cmd_struct.gen_include(include_file="cmd.h")

# Response structure
fields = [
    FieldInfo("trans_id", IntType(16)),
    FieldInfo("c", IntType(32)),
    FieldInfo("d", IntType(32)),
    FieldInfo("err_code", IntType(8))]
resp_struct = DataStructGen("Resp", fields)
resp_struct.stream_bus_widths = stream_bus_widths
resp_struct.gen_include(include_file="resp.h")