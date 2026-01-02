import matplotlib.pyplot as plt
import numpy as np
from vcdvcd import VCDVCD

from xilinxutils.timing import SigTimingInfo

def binary_str_to_numeric(
        bin_str : str,
        dtype : str,
        wid : int) -> int | float:
    """
    Converts a binary string to a numeric value of the specified type.
    Parameters
    ----------
    bin_str : str
        Binary string to convert (e.g., '1101').
    dtype : str
        Target data type ('int', 'uint' or 'float').
    wid : int
        Width of the data type string. (e.g, 8, 16, 32, 64).
    Returns
    -------
    value : int | float
        Converted numeric value.
    """

    # Zero pad the binary string to the specified width
    bin_str = bin_str.zfill(wid)

    if dtype == 'int':
        # Signed integer conversion
        if bin_str[0] == '1':  # negative number
            value = int(bin_str, 2) - (1 << wid)
        else:
            value = int(bin_str, 2)
    elif dtype == 'uint':
        # Unsigned integer conversion
        value = int(bin_str, 2)
    elif dtype == 'float':
        # Float conversion (assuming IEEE 754 format)
        if wid == 32:
            int_value = int(bin_str, 2)
            value = np.frombuffer(int_value.to_bytes(4, byteorder='big'), dtype=np.float32)[0]
        elif wid == 64:
            int_value = int(bin_str, 2)
            value = np.frombuffer(int_value.to_bytes(8, byteorder='big'), dtype=np.float64)[0]
    else:
        raise ValueError(f"Unsupported data type: {dtype}")
    return value

class SigInfo(object):
    """
    Class to hold information about a VCD signal.

    Attributes
    ----------
    name : str
        Full name of the signal.
    two_level : bool
        True if the signal is two-level (0 and 1).
    numeric_type  : str
        Type of numeric data ('str', 'int', 'uint', 'float').
    numeric_fmt_str : str
        Format string for numeric display.   If None, a default format is used.
    is_clock : bool
        True if the signal is identified as a clock.
    values : list of str
        List of signal values from the VCD file
    times : list of int
        List of time points corresponding to the signal values.
    disp_vals : list of str
        List of signals values for display (after formatting).
    short_name : str
        Short name of the signal (e.g., last part of full name).
    wid : int | None
        Bitwidth of the signal.  If None, the bitwidth will be inferred
        from the name.  For example, a signal named 'data[15:0]' has a bitwidth of 16.
    """
    def __init__(
            self,
            name : str,
            tv : list[tuple[int, str]],
            time_scale : float = 1e3,
            numeric_type : str = 'uint',
            numeric_fmt_str : None | str = None,
            wid : int | None = None):
        self.name = name
        self.two_level = False
        self.numeric_type = numeric_type # 'int', 'uint', 'float'
        self.numeric_fmt_str = numeric_fmt_str  
        self.is_clock = False
        self.time_scale = time_scale
        self.wid = wid

        # Get time and value lists
        n  = len(tv)
        self.times = np.zeros(n, dtype=float)
        self.values = []
        for i, (t, v) in enumerate(tv):
            self.values.append(v)
            self.times[i] = t / self.time_scale  # Scale time
        self.short_name = name.split('.')[-1]
        self.disp_values = None
        self.numeric_values = None

        self.set_format()

    def set_format(self):
        """
        Auto-detects the format of the signal based on its values.
        Right now this only works for Vivado-generated VCDs where the
        values are text strings.  
        
        The format can be over-written later if needed.
        """

        # Estimate the bitwidth if not provided
        if self.wid is None:
            parts = self.name.split('[')
            if len(parts) > 1:
                bit_range = parts[-1].strip(']')
                msb_lsb = bit_range.split(':')
                if len(msb_lsb) == 2:
                    msb = int(msb_lsb[0])
                    lsb = int(msb_lsb[1])
                    self.wid = abs(msb - lsb) + 1
                else:
                    self.wid = 1
            else:
                self.wid = 1
    
        # Remove un-specified values
        filtered = [v for v in self.values if v not in {'x', 'X', 'z', 'Z'}]

        # Check if all values are single-bit '0' or '1'
        if all(v in {'0', '1'} for v in filtered):
            self.two_level = True
            self.numeric_type  = 'uint'
            self.numeric_fmt_str = '%d'

        # Check if clock signal
        if self.name:
            name_lower = self.name.lower()
            if 'clock' in name_lower or 'clk' in name_lower:
                self.is_clock = True

        # Set the numeric format string if not provided
        if self.numeric_fmt_str is None:
            if self.numeric_type == 'int':
                self.numeric_fmt_str = f"%d"
            elif self.numeric_type == 'uint':
                self.numeric_fmt_str = f"%X"
            elif self.numeric_type == 'float':
                self.numeric_fmt_str = f"%.3f"
            else:
                self.numeric_fmt_str = "%s"  # default to string

    def get_values(self):
        """
        Converts the signal numeric and display values based on the format.   
        """

        # Return if already computed
        if self.disp_values is not None and self.numeric_values is not None:
            return

        self.disp_values = []
        self.numeric_values = []
        for v in self.values:
            d = str(v)  # Default is to  display original value
            num_value = 0
            if not (v in {'x', 'X', 'z', 'Z'}):
                num_value = binary_str_to_numeric(
                    v, self.numeric_type, self.wid)
                d = self.numeric_fmt_str % num_value                    
            self.numeric_values.append(num_value)
            self.disp_values.append(d)
        self.numeric_values = np.array(self.numeric_values).astype(np.uint32)

    


class VcdParser(object):
    """
    Class to parse VCD signals and extract information.

    Attributes
    ----------
    sig_info : dict[str, SigInfo]
        Information for each signal to be processed.
    time_scale : float
        Time scaling factor (default: 1e3 for ns).
    """
    def __init__(
            self, 
            vcd : VCDVCD):
        """
        Parameters
        ----------
        vcd : VCDVCD
            Parsed VCD object to initialize the viewer.
        """

        self.vcd = vcd        
        self.sig_info = dict()
        self.time_scale = 1e3  # default to ns

  
    def add_signal(
            self,
            name : str,
            short_name : str | None = None,
            numeric_type : str | None = None,
            numeric_fmt_str : str | None = None):
        """ 
        Adds a signal to be processed

        Parameters
        ----------
        name : str
            Full name of the signal to add.
        short_name : str | None
            Short name to use for the signal.  If None, the last part of the full name is used.
        numeric_type : str | None
            Numeric type of the signal ('int', 'uint', 'float').
        numeric_fmt_str : str | None
            Format string for displaying the numeric values.
        """
        for s in self.vcd.signals:
            if s == name:
                sig_info = SigInfo(
                    name, 
                    self.vcd[s].tv, 
                    time_scale=self.time_scale,
                    numeric_type=numeric_type,
                    numeric_fmt_str=numeric_fmt_str)
                self.sig_info[s] = sig_info                
                if short_name is not None:
                    self.sig_info[s].short_name = short_name
                return
        raise ValueError(f"Signal '{name}' not found in VCD.")

    def add_saxi_signals(self):
        """ 
        Adds the s_axi_control signals to the signal list
        """
        prefix = 's_axi_control'
        for s in self.vcd.signals:
            if prefix in s:
                short_name = s.split(f"{prefix}_")[-1]
                self.add_signal(s)
                self.sig_info[s].short_name = short_name
       
    def add_clock_signal(
            self, 
            name : str | None = None) -> str:
        """
        Adds a clock signal to sig_info and marks it as a clock.
        Parameters
        ----------
        name : str
            Name that must be contained in the signal along with 'clock' or 'clk' to be added.

        Returns
        -------
        full_name : str
            Full name of the clock signal added.
        """
        for s in self.vcd.signals:
            name_lower = s.lower()
            if (('clock' in name_lower) or ('clk' in name_lower)) and (name is None or name in s):
                name = s
                break
        if name is None:
            raise ValueError("No clock signal found in VCD.")
        self.add_signal(name)
        self.sig_info[name].is_clock = True
        self.sig_info[name].short_name =  'clk'

        return name

    def add_status_signals(
            self, 
            prefix : str ='AESL_'):
        """
        Adds the status signals to disp_signals.

        Following the Vivado HLS naming convention, the signals added 
        are those ending with {prefix} + one of
        'clock', 'start', 'done', 'idle', 'ready'.

        Parameters
        ----------
        prefix : str
            Prefix for the status signals
        """
        suffixes = ['clock', 'start', 'done', 'idle', 'ready']
        for s in self.vcd.signals:
            for suf in suffixes:
                if s.endswith(f"{prefix}{suf}"):
                    self.add_signal(s)
                    self.sig_info[s].short_name = suf

    def add_axiss_signals(
            self,
            name : str | None = None,
            short_name_prefix : str | None = None) -> dict[str, str]:
        """
        Adds signals that are part of an AXI4-Stream interface.

        Parameters
        ----------
        name : str | None
            If provided, only signals containing this substring are considered.
        short_name_prefix : str | None
            If provided, this prefix is added to the short names of the signals.

        Returns
        -------
        axi_sigs : dict[str, str]
            Dictionary mapping AXI4-Stream keywords to signal names.
        bitwidth : int
            Bitwidth of the TDATA signal.
        """
        axi4s_keywords = ['tdata', 'tvalid', 'tready', 'tlast']
        axi_sigs = dict()
        for kw in axi4s_keywords:
            axi_sigs[kw] = None
            for s in self.vcd.signals:
                if kw in s.lower() and (name is None or name in s):
                    if axi_sigs[kw] is not None:
                        raise ValueError(f"Multiple signals found for AXI4-Stream keyword '{kw}'.")
                    axi_sigs[kw] = s
                    self.add_signal(s)
                    if short_name_prefix:
                        short_name = f"{short_name_prefix}_{kw.upper()}"
                    elif name:
                        short_name = f"{name}_{kw.upper()}"
                    else:  
                        short_name = kw.upper()
                    self.sig_info[s].short_name = short_name
            if axi_sigs[kw] is None:
                raise ValueError(f"No signal found for AXI4-Stream keyword '{kw}'.")
            
        # Get the bitwidth from the TDATA signal.
        # The signal ends in [N:0], so the width is N+1
        tdata_sig = axi_sigs['tdata']
        tdata_parts = tdata_sig.split('[')
        bitwidth = None
        if len(tdata_parts) > 1:
            bit_range = tdata_parts[-1].strip(']')
            msb_lsb = bit_range.split(':')
            if len(msb_lsb) == 2:
                msb = int(msb_lsb[0])
                bitwidth = msb + 1       

        if bitwidth is None:
            raise ValueError(f"Could not determine bitwidth from TDATA signal '{tdata_sig}'.")   
                  
        return axi_sigs, bitwidth

   
    def full_name(
            self, 
            short_name : str) -> str:
        """
        Returns the full signal name for a given short name.
        Parameters
        ----------
        short_name : str
            Short name of the signal
        Returns
        -------
        full_name : str
            Full signal name if found, else None
        """
        for s, si in self.sig_info.items():
            if si.short_name == short_name:
                return s
        return None
    
    def get_values(
            self):
        """
        Converts the signal values for all added signals.
        """
        for s, si in self.sig_info.items():
            si.get_values()

    def get_td_signals(
            self) -> dict[str, SigTimingInfo]:
        """
        Returns the information for all added signals so that this can be 
        used for the timing diagram plotting.

        Example
        -------
        from vcd import VcdParser
        from timing import TimingDiagram

        vp = VcdParser(vcd)
        vp.add_signal(...)  # Add all signals to be plotted
        ...
        sig_list = vp.get_td_signals()
        td = TimingDiagram()
        td.add_signals(sig_list)
        td.plot()
        

        Returns
        -------
        sig_list : list[SigTimingInfo]
            List of signal timing information.
        """

        self.get_values()

        sig_list = []
        for si in self.sig_info.values():
            td_si = SigTimingInfo(
                name = si.short_name,
                times = si.times,
                values = si.disp_values,
                is_clock = si.is_clock)
            sig_list.append(td_si)
        return sig_list

    

    def extract_axis_bursts(
            self,
            clk_name : str,
            axis_sigs : dict[str, str]) -> list[dict]:
        """
        Extract bursts from AXI4-Stream signals.
        
        Parameters
        ----------
        clk_name: str
            Name of the clock signal.
        axis_sigs : dict[str, str]
            Dictionary of AXI4-Stream signal names with keys:
            'tdata', 'tvalid', 'tready', 'tlast'

        Returns
        -------
        bursts : list of dict
            Each dict has:
            - 'data': list of tdata values in the burst
            - 'start_idx': index of first beat in burst
            - 'beat_type':  list of status of each beat.
            beat_type[i] can be 0 (transfer, tvalid=tready=1), 1 (idle (tvalid=0)), 2 (stall (tready=0))
            - 'tstart': time of first beat in burst
        clk_period : float
            Estimated clock period in ns.
            Hence the time for beat i is tstart + i * clk_period
        """
        bursts = []
        current_burst = None

        # Extract clock times and resample AXI-Stream signals
        clk_sig = self.sig_info[clk_name]
        clk_times = extract_clock_times(clk_sig)
        tdata = resample_signal(self.sig_info[axis_sigs['tdata']], clk_times)
        tvalid = resample_signal(self.sig_info[axis_sigs['tvalid']], clk_times)
        tready = resample_signal(self.sig_info[axis_sigs['tready']], clk_times)
        tlast = resample_signal(self.sig_info[axis_sigs['tlast']]  , clk_times)

        for i in range(len(tdata)):
            # Handshake occurs only when both valid and ready are high
            if tvalid[i] and tready[i]:
                if current_burst is None:
                    # Start a new burst
                    current_burst = {
                        'data': [],
                        'start_idx': i,
                        'beat_type': [],
                        'tstart': clk_times[i]

                    }
                # Append this beat
                current_burst['data'].append(tdata[i])
                current_burst['beat_type'].append(0)  # transfer

                if tlast[i]:
                    # End of burst
                    current_burst['data'] = np.array(current_burst['data']).astype(np.uint32)
                    bursts.append(current_burst)
                    current_burst = None
            else:
                if current_burst is not None:
                    if not tvalid[i]:
                        current_burst['beat_type'].append(1)  # idle
                    elif not tready[i]:
                        current_burst['beat_type'].append(2)  # stall
                # Stall or idle → skip
                continue

        # Estimate clock period
        clk_diffs = np.diff(clk_times)
        clk_period = np.median(clk_diffs)

        return bursts, clk_period


def extract_clock_times(
        sig_info : SigInfo) -> list[float]:
    """
    Extracts the clock edge times from a VCD object for a given clock signal.

    Parameters
    ----------
    vcd : VCDVCD
        Parsed VCD object.
    clk_name : str
        Name of the clock signal.

    Returns
    -------
    clk_times : list of float
        List of times (in ns) when the clock signal transitions to '1'.
    """
    
    clk_times = []
    for t, v in zip(sig_info.times, sig_info.values):
        if v == '1':
            clk_times.append(t)  # Convert to ns

    clk_times = np.array(clk_times)

    return clk_times

def resample_signal(
        sig_info : SigInfo,
        clk_times : np.ndarray) -> np.ndarray:
    """
    Resamples a signal to new time points using nearest-neighbor interpolation.

    Parameters
    ----------
    sig_info : SigInfo
        Signal information object.
    new_times : np.ndarray
        Array of new time points to sample the signal at.  Typically these are clock edge times.

    Returns
    -------
    resampled_values : np.ndarray
        Array of signal values at the new time points.
    """    
    sig_times = sig_info.times
    sig_values = sig_info.numeric_values
    sampled = np.empty_like(clk_times, dtype=sig_values.dtype)

    j = 0  # pointer into sig_times and sig_values
    current_val = sig_values[0]

    for i, t_clk in enumerate(clk_times):
        # advance signal pointer while events are before or at this clock
        while j < len(sig_times) and sig_times[j] <= t_clk:
            current_val = sig_values[j]
            j += 1
        sampled[i] = current_val

    return sampled

