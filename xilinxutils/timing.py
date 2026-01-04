# timing.py: Helper functions for timing analysis of Xilinx designs

import numpy as np
import matplotlib.pyplot as plt

class SigTimingInfo(object):
    """    
    Holds timing information for a single signal.
    """
    def __init__(
            self, 
            name : str, 
            times : list[float], 
            values : list[str], 
            is_clock : bool =False):
        """
        Constructor
        
        Parameters
        ----------
        name : str
            Display name of the signal.
        times : list of float
            List of time points where the signal changes value.
        values : list of str
            List of signal values corresponding to the time points.
        is_clock : bool, optional
            If True, indicates that this signal is a clock.
        """
        self.name = name
        self.times = times
        self.values = values
        self.is_clock = is_clock
        self.two_level = all(v in {'0', '1'} for v in values)

class ClkSig(SigTimingInfo):
    def __init__(
            self,
            clk_name : str = 'clk',
            period : float = 10.0,
            ncycles : int = 10,
            start_rising : bool = True): 
        """
        Constructor for clock signal information.
        Parameters
        ----------
        clk_name : str, optional
            Name of the clock signal.
        period : float, optional
            Clock period in time units.
        ncycles : int, optional
            Number of clock cycles.
        """
        self.ncycles = ncycles
        self.period = period
        times = np.arange(0, 2*ncycles) * (period / 2)
        if start_rising:
            values = ['1', '0'] * ncycles
        else:
            values = ['0', '1'] * ncycles 
        super().__init__(name=clk_name, times=times, values=values, is_clock=True)

    def clk_periods(self):
        """
        Returns the start of each clock period, as defined by the rising edges.
        """
        edges = []
        if self.values[0] == '1':
            edges.append(self.times[0])
        for i in range(1, len(self.values)):
            if self.values[i-1] == '0' and self.values[i] == '1':
                edges.append(self.times[i])
        return edges



class TimingDiagram(object):
    def __init__(
            self, 
            time_unit='ns'):
        self.sig_info = dict()
        self.time_unit = time_unit

    def add_signal(self, sig_info : SigTimingInfo):
        """
        Adds a signal's timing information to the diagram.

        Parameters
        ----------
        sig_info : SigTimingInfo
            Signal timing information to add.
        """
        self.sig_info[sig_info.name] = sig_info

    def add_signals(self,
                    sig_info_list : list[SigTimingInfo]):
        """
        Adds multiple signals' timing information to the diagram.

        Parameters
        ----------
        sig_info_list : list of SigTimingInfo
            List of signal timing information to add.
        """
        for si in sig_info_list:
            self.add_signal(si)

    def plot_signals(
            self,
            add_clk_grid = True,
            ax = None,
            fig_width = 10,
            row_height = 0.5,
            row_step = 0.8,
            trange = None,
            text_mode = 'always',
            text_scale_factor = 1000):
        """
        Plots the timing diagram for the selected signals.

        Parameters
        ----------
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
        trange : tuple(float, float), optional
            Time range (tmin, tmax) to plot. If None, uses full range of signals.
        text_mode : str, optional
            Mode for drawing text labels. Options are 'always', 'never', 'auto'.
            In 'auto' mode, text is drawn only if there is enough space.
        text_scale_factor : float, optional
            Scale factor to determine if there is enough space to draw text labels.

        Returns 
        -------
        None         
        ax : matplotlib.axes.Axes
            Axes object with the plotted signals.   
        """

        # Determine signals to plot
        signals_to_plot = list(self.sig_info.keys())    

    
        # Create figure and axis if not provided
        nsig = len(signals_to_plot)
        ymax = row_step * nsig
        if ax is None:
            ax_provided = False
            fig_height = row_height * nsig
            fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        else:
            ax_provided = True


        # Get min and max times.  If not provided, compute from signals
        if trange is not None:
            tmin, tmax = trange
        else:
            for i, s in enumerate(signals_to_plot):
                si = self.sig_info[s]
                if i == 0:
                    tmin = si.times[0]
                    tmax = si.times[-1]
                else:
                    tmin = min(tmin, si.times[0])
                    tmax = max(tmax, si.times[-1])   

        # Save the top and bottom y positions for each signal
        self.ytop = dict()
        self.ybot = dict()

        for i, s in enumerate(signals_to_plot):
            y =  ymax - (i + 0.5) * row_step  # vertical position for signal s
            si = self.sig_info[s]
            t_list = si.times 

            # Draw signal name
            ax.text(tmin - 0.5, y, s, ha='right', va='center', fontsize=10)

            # Set the top and bottom y positions for the signal
            ybot = y - 0.4 * row_step
            ytop = y + 0.4 * row_step
            self.ytop[s] = ytop
            self.ybot[s] = ybot


            # Draw horizontal segments between value changes
            vlast = None
            for j in range(len(t_list)):
                t_start = t_list[j]
                if j + 1 < len(t_list):
                    t_end = t_list[j + 1]
                else:
                    t_end = tmax  # Extend to the right edge

                # Skip if outside time range
                if t_end < tmin or t_start > tmax:
                    continue
                t_start = max(tmin, t_start)
                t_end = min(tmax, t_end)

                v = si.values[j]

                # Set default drawing options
                draw_top = True
                draw_bot = True
                draw_text = True
                fill_gray = False
                draw_vert = True

                # Adjust drawing options based on value
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
                    if vlast is not None:
                        if v == vlast:
                            draw_vert = False
                    elif si.two_level:  # For two level signals, no vertical line at start
                        draw_vert = False
                vlast = v
    
                # Draw a vertical line at the start of the segment                
                if draw_vert:
                    ax.vlines(t_start, ybot, ytop, color='black', linewidth=1)
                if draw_bot:
                    ax.hlines(ybot, t_start, t_end, color='black', linewidth=1)
                if draw_top:
                    ax.hlines(ytop, t_start, t_end, color='black', linewidth=1)

                # Fill gray for unknown values
                if fill_gray:
                    ax.fill_betweenx([ybot, ytop], t_start, t_end, color='lightgray')

                # Place text label in the middle of the segment
                # Check if there is enough space to draw the text
                if text_mode == 'never':
                    draw_text = False
                if draw_text and text_mode == 'auto':
                    idx_start = ax.transData.transform((t_start, y))
                    idx_end = ax.transData.transform((t_end, y))
                    if idx_end[0] - idx_start[0] < len(v)*text_scale_factor:
                        draw_text = False
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
                add_clk_grid = False
                
        if add_clk_grid:
            for i, t in enumerate(si.times):
                v = si.values[i]
                if v == '1' and (tmin <= t) and (t <= tmax):
                    ax.axvline(x=t, color='gray', linestyle='--', linewidth=0.5)

        ax.set_yticks([])
        ax.set_xlim(tmin, tmax)
        ax.set_ylim(0, ymax)


        return ax