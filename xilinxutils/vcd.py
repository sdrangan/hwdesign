import matplotlib.pyplot as plt
import numpy as np
from vcdvcd import VCDVCD

class SigInfo(object):
    """
    Class to hold information about a VCD signal.

    Attributes
    ----------
    name : str
        Full name of the signal.
    two_level : bool
        True if the signal is two-level (0 and 1).
    vcd_fmt : str
        Format of the signal in VCD ('str' or 'binary').
        Later we will add numeric formats
    numeric_type  : str
        Type of numeric data ('str', 'int', 'float').
    numeric_fmt_str : str
        Format string for numeric display.  
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
    """
    def __init__(
            self,
            name : str,
            tv : list[tuple[int, str]],
            time_scale : float = 1e3):
        self.name = name
        self.two_level = False
        self.vcd_fmt = 'str' # 'str' or 'binary'
        self.numeric_type = 'str' # 'str', 'int', 'float', 'hex'
        self.numeric_fmt_str = '%d'  
        self.is_clock = False
        self.time_scale = time_scale

        # Get time and value lists
        n  = len(tv)
        self.times = np.zeros(n, dtype=float)
        self.values = []
        for i, (t, v) in enumerate(tv):
            self.values.append(v)
            self.times[i] = t / self.time_scale  # Scale time
        self.short_name = name.split('.')[-1]
        self.disp_values = None

        self.set_format()

    def set_format(self):
        """
        Auto-detects the format of the signal based on its values.
        Right now this only works for Vivado-generated VCDs where the
        values are text strings.  
        
        The format can be over-written later if needed.
        """
    
        # Remove un-specified values
        filtered = [v for v in self.values if v not in {'x', 'X', 'z', 'Z'}]

        # Check if all values are single-bit '0' or '1'
        if all(v in {'0', '1'} for v in filtered):
            self.two_level = True
            self.numeric_type  = 'int'
            self.numeric_fmt_str = '%d'
            self.vcd_fmt = 'binary'

        # Check if all values are strings composed only of '0' and '1's
        elif all(set(v).issubset({'0', '1'}) for v in filtered):
            self.vcd_fmt = 'binary'
            self.numeric_type  = 'int'

        # Check if clock signal
        if self.name:
            name_lower = self.name.lower()
            if 'clock' in name_lower or 'clk' in name_lower:
                self.is_clock = True

    def get_display_values(self):
        """
        Converts the signal values to display format based on the detected format.   

        Right now, `float` is not implemented.
        """
        self.disp_values = []
        for v in self.values:
            d = str(v)  # Default is to  display original value
            if not (v in {'x', 'X', 'z', 'Z'}):
                if self.vcd_fmt == 'binary':
                    if self.numeric_type == 'int':
                        int_value = int(v, 2)
                        d = self.numeric_fmt_str % int_value
            self.disp_values.append(d)


class VcdViewer(object):
    """
    Class to view VCD signals and plot timing diagrams.

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

  
    def add_signal(self, 
                   name : str):
        """ 
        Adds a signal to be processed
        """
        for s in self.vcd.signals:
            if s == name:
                sig_info = SigInfo(name, self.vcd[s].tv, self.time_scale)
                self.sig_info[s] = sig_info                
                return
        raise ValueError(f"Signal '{name}' not found in VCD.")

    def add_saxi_signals(self):
        """ 
        Adds the s_axi_control signals to disp_signals. 
        """
        prefix = 's_axi_control'
        for s in self.vcd.signals:
            if prefix in s:
                short_name = s.split(f"{prefix}_")[-1]
                self.add_signal(s)
                self.sig_info[s].short_name = short_name
       
    
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
    
    
    def plot_signals(
            self,
            short_names = None,
            add_clk_grid = True,
            ax = None,
            fig_width = 10,
            row_height = 0.5,
            row_step = 0.8,
            left_border = None,
            right_border = None):
        """
        Plots the timing diagram for the selected signals.

        Parameters
        ----------
        short_names : list of str, optional
            List of short names of signals to plot. If None, plots all signals.
        add_clk_grid : bool, optional
            If True, adds vertical grid lines at clock edges. 
        ax : matplotlib.axes.Axes, optional
            Axes object to plot on. If None, a new figure and axes are created.
        fig_width : float, optional
            Width of the figure in inches (if ax is None).
        row_height : float, optional    
            Height of each row in inches.  
        row_step : float, optional
            Vertical spacing between rows.
        left_border : float, optional
            Left border space in time units. If None, set to 10% of time range.
        right_border : float, optional
            Right border space in time units. If None, set to 5% of time range.
        Returns 
        -------
        None         
        ax : matplotlib.axes.Axes
            Axes object with the plotted signals.   
        """

        # Determine signals to plot
        if short_names is None:
            signals_to_plot = list(self.sig_info.keys())    
        else:
            sig_found = {sn: False for sn in short_names}
            signals_to_plot = []
            for s, si in self.sig_info.items():
                if si.short_name in short_names:
                    sn = si.short_name  
                    sig_found[sn] = True
                    signals_to_plot.append(s)
            for sn, found in sig_found.items():
                if not found:
                    print(f"Warning: Signal with short name '{sn}' not found.")

        
    
        # Create figure and axis if not provided
        nsig = len(signals_to_plot)
        ymax = row_step * nsig
        if ax is None:
            ax_provided = False
            fig_height = row_height * nsig
            fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        else:
            ax_provided = True


        # Get min and max times
        for i, s in enumerate(signals_to_plot):
            si = self.sig_info[s]
            if i == 0:
                tmin = si.times[0]
                tmax = si.times[-1]
            else:
                tmin = min(tmin, si.times[0])
                tmax = max(tmax, si.times[-1])   

        # Compute the borders if not provided as a fration of total time range
        # Default is left border = 15% of time range, right border = 5% of time range
        # This gives space for signal names on the left
        time_range = tmax - tmin        
        if left_border is None:
            left_border = 0.10 * time_range
        if right_border is None:
            right_border = 0.05 * time_range

        for i, s in enumerate(signals_to_plot):
            y =  ymax - (i + 0.5) * row_step  # vertical position for signal s
            si = self.sig_info[s]
            t_list = si.times 
            sn = si.short_name

            # Get the display values
            si.get_display_values()
            v_list = si.disp_values
            
            # Draw signal name
            ax.text(tmin - 0.5, y, sn, ha='right', va='center', fontsize=10)

            # Draw horizontal segments between value changes
            for j in range(len(t_list)):
                t_start = t_list[j]
                if j + 1 < len(t_list):
                    t_end = t_list[j + 1]
                else:
                    t_end = tmax  # Extend to the right edge
                v = v_list[j]

                draw_top = True
                draw_bot = True
                draw_text = True
                fill_gray = False
                if (v in {'x', 'X', 'z', 'Z'}):
                    draw_text = False
                    fill_gray = True
                if (si.two_level):
                    if v == '1':
                        draw_bot = False
                        draw_text = False
                    elif v == '0':
                        draw_top = False
                        draw_text = False
    
                # Draw a vertical line at the start of the segment
                ybot = y - 0.4 * row_step
                ytop = y + 0.4 * row_step
                ax.vlines(t_start, ybot, ytop, color='black', linewidth=1)
                if draw_bot:
                    ax.hlines(ybot, t_start, t_end, color='black', linewidth=1)
                if draw_top:
                    ax.hlines(ytop, t_start, t_end, color='black', linewidth=1)

                # Fill gray for unknown values
                if fill_gray:
                    ax.fill_betweenx([ybot, ytop], t_start, t_end, color='lightgray')

                # Place text label in the middle of the segment
                if draw_text:
                    ax.text((t_start + t_end) / 2, y, v, ha='center', va='center',
                            fontsize=10, color='black')


        # Add clock grid lines if requested
        if add_clk_grid:
            clk_signal = None
            for s, si in self.sig_info.items():
                if si.is_clock:
                    clk_signal = si.name
                    break
            if not clk_signal:
                raise ValueError("No clock signal found in disp_signals for grid lines.")

            for i, t in enumerate(si.times):
                v = si.values[i]
                if v == '1':
                    ax.axvline(x=t, color='gray', linestyle='--', linewidth=0.5)

        ax.set_yticks([])
        ax.set_xlim(tmin - left_border, tmax + right_border)
        ax.set_ylim(0, ymax)


        return ax
