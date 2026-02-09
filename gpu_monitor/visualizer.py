from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Label
from textual.containers import Container, Vertical, Horizontal, Grid, VerticalScroll
from textual import events, work
from textual.reactive import reactive
from rich.text import Text
from rich.style import Style
import os
import time
from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta
from pathlib import Path

from .utils import parse_log_file, parse_log_file_incremental, format_timestamp, parse_timestamp
from .plotter import create_plot

# ═══════════════════════════════════════════════════════════════════════════════
# GRUVBOX DARK THEME - 256 COLOR PALETTE (tmux compatible)
# ═══════════════════════════════════════════════════════════════════════════════
# Background:  bg0=235, bg1=237, bg2=239, bg3=241, bg4=243
# Foreground:  fg=223, fg4=246
# Accents:     red=167, green=142, yellow=214, blue=109
#              purple=175, aqua=108, orange=208
# ═══════════════════════════════════════════════════════════════════════════════

# Gruvbox 256-color constants
GRV_BG0 = "color(235)"      # #282828
GRV_BG1 = "color(237)"      # #3c3836
GRV_BG2 = "color(239)"      # #504945
GRV_BG3 = "color(241)"      # #665c54
GRV_BG4 = "color(243)"      # #7c6f64
GRV_FG = "color(223)"       # #ebdbb2
GRV_FG4 = "color(246)"      # #a89984
GRV_RED = "color(167)"      # #fb4934
GRV_GREEN = "color(142)"    # #b8bb26
GRV_YELLOW = "color(214)"   # #fabd2f
GRV_BLUE = "color(109)"     # #83a598
GRV_PURPLE = "color(175)"   # #d3869b
GRV_AQUA = "color(108)"     # #8ec07c
GRV_ORANGE = "color(208)"   # #fe8019


class Sparkline(Static):
    """A compact sparkline chart widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.values = []
        self.color = GRV_AQUA

    def update_values(self, values, color=None):
        """Update sparkline with new values. Uses Gruvbox aqua by default."""
        if color is None:
            color = GRV_AQUA
        self.values = values[-60:] if len(values) > 60 else values  # Keep last 60 points
        self.color = color
        self.refresh()

    def render(self) -> Text:
        """Render sparkline using block characters."""
        if not self.values:
            return Text("" * 30, style=GRV_FG4)

        # Sparkline characters
        chars = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']

        max_val = max(self.values) if self.values else 1
        min_val = min(self.values) if self.values else 0
        range_val = max_val - min_val if max_val != min_val else 1

        sparkline = []
        for val in self.values:
            normalized = (val - min_val) / range_val if range_val > 0 else 0
            idx = min(int(normalized * len(chars)), len(chars) - 1)
            sparkline.append(chars[idx])

        return Text(''.join(sparkline), style=self.color)


class MetricBar(Static):
    """A horizontal progress bar with gradient colors."""

    def __init__(self, label, unit, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label = label
        self.unit = unit
        self.value = 0
        self.max_value = 100

    def update_value(self, value, max_value=100):
        """Update bar value."""
        self.value = value
        self.max_value = max_value
        self.refresh()

    def render(self) -> Text:
        """Render progress bar with colors."""
        width = 30
        percentage = (self.value / self.max_value) if self.max_value > 0 else 0
        filled = int(width * percentage)

        # Color based on percentage - Gruvbox colors
        if percentage < 0.5:
            color = GRV_GREEN
        elif percentage < 0.75:
            color = GRV_YELLOW
        else:
            color = GRV_RED

        # Create bar
        bar = '█' * filled + '░' * (width - filled)

        # Format value display
        if self.unit == "%":
            value_str = f"{self.value:.0f}{self.unit}"
        elif self.unit == "GB":
            value_str = f"{self.value:.1f}/{self.max_value:.1f}{self.unit}"
        elif self.unit == "°C":
            value_str = f"{self.value:.0f}{self.unit}"
        elif self.unit == "W":
            value_str = f"{self.value:.0f}{self.unit}"
        else:
            value_str = f"{self.value:.1f}{self.unit}"

        text = Text()
        text.append(f"{self.label:8s} ", style=f"bold {GRV_AQUA}")
        text.append(bar, style=color)
        text.append(f" {value_str}", style=f"bold {color}")

        return text


class GPUCard(Static):
    """A beautiful card displaying metrics for a single GPU."""

    def __init__(self, gpu_id, show_gpu=False, show_mem=True, show_temp=False, show_power=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gpu_id = gpu_id
        self.metrics = None
        self.history = []
        self.show_gpu = show_gpu
        self.show_mem = show_mem
        self.show_temp = show_temp
        self.show_power = show_power

    def update_metrics(self, metrics, history):
        """Update GPU card with latest metrics."""
        self.metrics = metrics
        self.history = history
        self.refresh()

    def render(self) -> Text:
        """Render the GPU card content with beautiful styling."""
        from .plotter import create_progress_bar, create_sparkline

        text = Text()

        if not self.metrics:
            text.append(f"  GPU {self.gpu_id}", style=f"bold {GRV_AQUA}")
            text.append(" │ ", style=GRV_BG4)
            text.append("Waiting for data...", style=f"italic {GRV_FG4}")
            return text

        metrics = self.metrics

        # ═══════════════════════════════════════════════════════════
        # HEADER: GPU ID + Status
        # ═══════════════════════════════════════════════════════════
        util = metrics['utilization_gpu']

        # Status indicator with icon (Gruvbox colors)
        if util > 80:
            status_icon = "●"
            status_color = GRV_RED
            status_text = "HIGH"
        elif util > 30:
            status_icon = "●"
            status_color = GRV_YELLOW
            status_text = "ACTIVE"
        else:
            status_icon = "●"
            status_color = GRV_GREEN
            status_text = "IDLE"

        text.append(f" GPU {self.gpu_id}", style=f"bold {GRV_FG}")
        text.append(" │ ", style=GRV_BG4)
        text.append(f"{status_icon} ", style=f"bold {status_color}")
        text.append(f"{status_text}", style=status_color)
        text.append("\n")

        # Process info on its own row
        process_info = metrics.get('process_info', '')
        if process_info:
            text.append(" ⚙ ", style=GRV_FG4)
            text.append(f"{process_info}", style=GRV_PURPLE)
            text.append("\n")

        # ═══════════════════════════════════════════════════════════
        # METRICS BAR: Compact view of all metrics with progress bars
        # ═══════════════════════════════════════════════════════════
        mem_used = metrics['memory_used'] / 1024
        mem_total = metrics['memory_total'] / 1024
        temp = metrics['temperature']
        power = metrics['power_draw']

        # GPU and Memory on same line (smaller bars) - Gruvbox colors
        text.append(" GPU ", style=GRV_FG4)
        text.append_text(create_progress_bar(util, 100, width=8, show_percent=False))
        util_color = GRV_RED if util > 80 else (GRV_YELLOW if util > 30 else GRV_GREEN)
        text.append(f"{util:4.0f}%", style=f"bold {util_color}")

        text.append(" │ ", style=GRV_BG4)
        text.append("MEM ", style=GRV_FG4)
        mem_pct = (mem_used / mem_total * 100) if mem_total > 0 else 0
        text.append_text(create_progress_bar(mem_used, mem_total, width=8, show_percent=False))
        mem_color = GRV_RED if mem_pct > 80 else (GRV_YELLOW if mem_pct > 60 else GRV_GREEN)
        text.append(f"{mem_used:4.0f}G", style=f"bold {mem_color}")

        text.append("\n")

        # Temperature and Power on second line (smaller bars) - Gruvbox colors
        text.append(" TMP ", style=GRV_FG4)
        text.append_text(create_progress_bar(temp, 100, width=8, show_percent=False))
        temp_color = GRV_RED if temp > 80 else (GRV_YELLOW if temp > 65 else GRV_GREEN)
        text.append(f"{temp:4.0f}°", style=f"bold {temp_color}")

        text.append(" │ ", style=GRV_BG4)
        text.append("PWR ", style=GRV_FG4)
        text.append_text(create_progress_bar(power, 400, width=8, show_percent=False))
        power_color = GRV_RED if power > 300 else (GRV_YELLOW if power > 200 else GRV_GREEN)
        text.append(f"{power:4.0f}W", style=f"bold {power_color}")

        text.append("\n")

        # ═══════════════════════════════════════════════════════════
        # GRAPH: High-resolution Braille plot
        # ═══════════════════════════════════════════════════════════
        if self.history:
            timestamps = [p['_ts'] for p in self.history]
            process_names = [p.get('process_info', '') for p in self.history]

            text.append(" ───────────────────────────────────────────────\n", style=GRV_BG3)

            if self.show_gpu:
                util_values = [p['utilization_gpu'] for p in self.history]
                plot_text = create_plot(util_values, timestamps, "util", "GPU", "%",
                                       width=50, height=5, process_names=process_names)
                text.append_text(plot_text)

            if self.show_mem:
                mem_values = [p['memory_used'] / 1024 for p in self.history]
                plot_text = create_plot(mem_values, timestamps, "mem", "MEM", "GB",
                                       width=50, height=5, process_names=process_names)
                text.append_text(plot_text)

            if self.show_temp:
                temp_values = [p['temperature'] for p in self.history]
                plot_text = create_plot(temp_values, timestamps, "temp", "TMP", "°C",
                                       width=50, height=5, process_names=process_names)
                text.append_text(plot_text)

            if self.show_power:
                power_values = [p['power_draw'] for p in self.history]
                plot_text = create_plot(power_values, timestamps, "power", "PWR", "W",
                                       width=50, height=5, process_names=process_names)
                text.append_text(plot_text)

        return text


class GPUMonitorApp(App):
    """Main Textual application for GPU monitoring with enhanced aesthetics."""

    # ═══════════════════════════════════════════════════════════════════════════
    # GRUVBOX DARK THEME - 256 COLOR CSS
    # ═══════════════════════════════════════════════════════════════════════════

    # Gruvbox Dark theme - hex colors mapped to 256-color by Textual
    # bg0=#282828, bg1=#3c3836, bg3=#665c54, yellow=#fabd2f
    CSS = """
    Screen {
        background: #282828;
    }

    Header {
        background: #3c3836;
        text-style: bold;
        height: 1;
    }

    Footer {
        background: #3c3836;
        height: 1;
    }

    #main-container {
        height: 1fr;
        padding: 0;
        background: #282828;
        scrollbar-gutter: stable;
    }

    #title-bar {
        height: 2;
        background: #3c3836;
        content-align: center middle;
        text-style: bold;
        border: none;
        margin: 0 1 0 1;
    }

    #gpu-grid {
        height: auto;
        layout: grid;
        grid-size: 2;
        grid-gutter: 0 1;
        padding: 0 1;
    }

    GPUCard {
        height: auto;
        min-height: 15;
        min-width: 56;
        background: #3c3836;
        border: solid #665c54;
        padding: 0 1;
    }

    GPUCard:hover {
        border: solid #fabd2f;
    }

    #controls {
        dock: bottom;
        height: 1;
        background: #3c3836;
        content-align: center middle;
        border-top: none;
    }

    .status-bar {
        background: #3c3836;
        height: auto;
        padding: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("left", "pan_left", "← Pan"),
        ("h", "pan_left", "← Pan"),
        ("right", "pan_right", "Pan →"),
        ("l", "pan_right", "Pan →"),
        ("minus", "zoom_out", "- Zoom"),
        ("plus", "zoom_in", "+ Zoom"),
        ("equal", "zoom_in", "+ Zoom"),
        ("j", "scroll_down", "↓ Scroll"),
        ("k", "scroll_up", "↑ Scroll"),
        ("ctrl+d", "page_down", "PgDn"),
        ("ctrl+u", "page_up", "PgUp"),
        ("g", "scroll_top", "Top"),
        ("G", "scroll_bottom", "Bottom"),
        ("home", "jump_start", "⟨⟨ Start"),
        ("end", "jump_end", "End ⟩⟩"),
        ("r", "reset_view", "⟲ Reset"),
        ("space", "toggle_pause", "⏯ Pause"),
    ]

    paused = reactive(False)

    def __init__(self, log_file, live_mode=False, show_gpu=False, show_mem=True,
                 show_temp=False, show_power=False):
        super().__init__()
        self.log_file = Path(log_file)
        self.live_mode = live_mode
        self.show_gpu = show_gpu
        self.show_mem = show_mem
        self.show_temp = show_temp
        self.show_power = show_power
        self.all_data = []
        self._timestamps = []  # Parallel list of datetime objects for bisect
        self._file_pos = 0  # Track file position for incremental reads
        self.view_start = None
        self.view_end = None
        self.default_window = 300  # 5 minutes
        self.last_update = 0
        self.update_interval = 1.0
        self.gpu_ids = []
        # following = True means view auto-scrolls with new data
        # following = False means view stays fixed (user panned away from "now")
        self.following = True
        self._scroll_container = None  # Cached for fast scrolling

    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Header()

        with VerticalScroll(id="main-container"):
            yield Static("", id="title-bar")

            with Grid(id="gpu-grid"):
                # GPU cards will be added dynamically
                pass

        yield Static("", id="controls")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize when app is mounted."""
        self.title = "GPU Monitor"

        # Cache scroll container for fast scrolling
        self._scroll_container = self.query_one("#main-container", VerticalScroll)

        self.update_title()
        self.update_grid_columns()

        # Load data in background thread to avoid blocking the UI
        self._start_async_load()

        if self.live_mode:
            self.set_interval(self.update_interval, self.update_live_data)

    @work(thread=True)
    def _start_async_load(self) -> None:
        """Load data in a background thread to avoid blocking the UI."""
        try:
            data = parse_log_file(self.log_file)
        except Exception:
            data = []
        file_pos = os.path.getsize(self.log_file) if self.log_file.exists() else 0
        self.call_from_thread(self._on_data_loaded, data, file_pos)

    def _on_data_loaded(self, data, file_pos):
        """Called on the main thread after data loading completes."""
        self.all_data = data
        self._file_pos = file_pos
        self._build_timestamp_index()

        if self.all_data and not self.gpu_ids:
            self.gpu_ids = sorted(set(point['gpu_id'] for point in self.all_data))

            # Add GPU cards
            grid = self.query_one("#gpu-grid", Grid)
            for gpu_id in self.gpu_ids:
                card = GPUCard(gpu_id, show_gpu=self.show_gpu, show_mem=self.show_mem,
                              show_temp=self.show_temp, show_power=self.show_power)
                card.id = f"gpu-card-{gpu_id}"
                grid.mount(card)

        self.reset_view()
        self.update_title()
        self.update_grid_columns()

        # Delay initial update to ensure widgets are fully mounted
        self.set_timer(0.1, self.update_plots)

    def _build_timestamp_index(self):
        """Build a sorted list of timestamps for binary search."""
        self._timestamps = [point['_ts'] for point in self.all_data]

    def on_resize(self, event) -> None:
        """Handle terminal resize."""
        self.update_grid_columns(event.size.width)

    def update_grid_columns(self, width=None):
        """Update grid columns based on terminal width."""
        # GPUCard min-width is 56, plus gutter and padding
        card_width = 60  # 56 + some padding/gutter

        if width is None:
            width = self.size.width

        # Calculate how many columns fit
        columns = max(1, width // card_width)

        # Debug: update title to show width and columns
        self.sub_title = f"w={width} cols={columns}"

        # Update grid style
        try:
            grid = self.query_one("#gpu-grid", Grid)
            grid.styles.grid_size_columns = columns
        except Exception:
            pass

    def update_title(self):
        """Update title bar with file info."""
        title_text = Text()

        # Clean, minimal title - Gruvbox colors
        title_text.append("  ◈ ", style=f"bold {GRV_YELLOW}")
        title_text.append("GPU Monitor", style=f"bold {GRV_FG}")
        title_text.append("  │  ", style=GRV_BG3)
        title_text.append(f"{len(self.gpu_ids)}", style=f"bold {GRV_GREEN}")
        title_text.append(" GPUs", style=GRV_GREEN)
        title_text.append("  │  ", style=GRV_BG3)
        title_text.append(f"{self.log_file.name}", style=GRV_FG4)

        if self.live_mode:
            title_text.append("  │  ", style=GRV_BG3)
            title_text.append("● ", style=f"bold {GRV_RED}")
            title_text.append("LIVE", style=GRV_RED)

        title_bar = self.query_one("#title-bar", Static)
        title_bar.update(title_text)

    def load_data(self):
        """Load data from log file."""
        try:
            self.all_data = parse_log_file(self.log_file)
            self._build_timestamp_index()
        except Exception as e:
            self.all_data = []
            self._timestamps = []

    def update_live_data(self):
        """Periodically read new data appended to the log file."""
        if not self.paused and self.live_mode:
            # Guard against file truncation/rotation
            try:
                current_size = os.path.getsize(self.log_file)
            except OSError:
                return

            if current_size < self._file_pos:
                # File was truncated/rotated, reload from scratch
                self.load_data()
                self._file_pos = current_size
            else:
                new_data, new_pos = parse_log_file_incremental(self.log_file, self._file_pos)
                if new_data:
                    self._file_pos = new_pos
                    self.all_data.extend(new_data)
                    self._timestamps.extend(point['_ts'] for point in new_data)

            # Create GPU cards if they don't exist yet (first data arrival)
            if self.all_data and not self.gpu_ids:
                self.gpu_ids = sorted(set(point['gpu_id'] for point in self.all_data))
                grid = self.query_one("#gpu-grid", Grid)
                for gpu_id in self.gpu_ids:
                    card = GPUCard(gpu_id, show_gpu=self.show_gpu, show_mem=self.show_mem,
                                  show_temp=self.show_temp, show_power=self.show_power)
                    card.id = f"gpu-card-{gpu_id}"
                    grid.mount(card)
                self.update_title()

            if self.all_data and self.following:
                # Only auto-scroll if following (user hasn't panned away)
                last_ts = self.all_data[-1]['_ts']
                window_size = self.view_end - self.view_start if self.view_end and self.view_start else timedelta(seconds=self.default_window)
                self.view_end = last_ts
                self.view_start = self.view_end - window_size

            self.update_plots()

    def reset_view(self):
        """Reset view to show last 60 seconds."""
        if not self.all_data:
            self.view_start = datetime.now() - timedelta(seconds=self.default_window)
            self.view_end = datetime.now()
        else:
            last_ts = self.all_data[-1]['_ts']
            self.view_end = last_ts
            self.view_start = self.view_end - timedelta(seconds=self.default_window)

        # Don't call update_plots here - let caller handle it
        # to avoid updating before widgets are mounted

    def get_visible_data(self):
        """Get data within the current view window using binary search."""
        if not self.all_data or not self.view_start or not self.view_end:
            return []

        lo = bisect_left(self._timestamps, self.view_start)
        hi = bisect_right(self._timestamps, self.view_end)
        return self.all_data[lo:hi]

    def update_plots(self):
        """Update all GPU cards with current view data."""
        visible_data = self.get_visible_data()

        if not visible_data:
            return

        # Group by GPU ID
        gpu_data = {}
        for point in visible_data:
            gpu_id = point['gpu_id']
            if gpu_id not in gpu_data:
                gpu_data[gpu_id] = []
            gpu_data[gpu_id].append(point)

        # Update each GPU card
        for gpu_id in self.gpu_ids:
            data = gpu_data.get(gpu_id, [])
            if data:
                try:
                    card = self.query_one(f"#gpu-card-{gpu_id}")
                    card.update_metrics(data[-1], data)
                except Exception as e:
                    pass

        # Update controls info - clean minimal style
        window_sec = (self.view_end - self.view_start).total_seconds()

        # Gruvbox themed controls
        controls_text = Text()
        controls_text.append("  ", style="")
        controls_text.append(f"{self.view_start.strftime('%H:%M:%S')}", style=GRV_FG4)
        controls_text.append(" → ", style=GRV_BG3)
        controls_text.append(f"{self.view_end.strftime('%H:%M:%S')}", style=GRV_FG4)
        controls_text.append(f"  {window_sec:.0f}s", style=GRV_BLUE)

        controls_text.append("  │  ", style=GRV_BG3)

        if self.paused:
            controls_text.append("▐▐ ", style=GRV_RED)
            controls_text.append("PAUSED", style=GRV_RED)
        elif self.live_mode and self.following:
            controls_text.append("● ", style=GRV_GREEN)
            controls_text.append("LIVE", style=GRV_GREEN)
        elif self.live_mode and not self.following:
            controls_text.append("◆ ", style=GRV_ORANGE)
            controls_text.append("HISTORY", style=GRV_ORANGE)
        else:
            controls_text.append("◼ ", style=GRV_BLUE)
            controls_text.append("STATIC", style=GRV_BLUE)

        controls_text.append("  │  ", style=GRV_BG3)
        controls_text.append(f"{len(visible_data)} samples", style=GRV_FG4)

        controls = self.query_one("#controls", Static)
        controls.update(controls_text)
        controls.refresh()

    def action_pan_left(self):
        """Pan view left (back in time). Disengages following mode."""
        if not self.all_data or not self.view_start or not self.view_end:
            return

        window_size = self.view_end - self.view_start
        shift = timedelta(seconds=window_size.total_seconds() * 0.02)  # 2% of window

        self.view_start -= shift
        self.view_end -= shift

        first_ts = self.all_data[0]['_ts']
        if self.view_start < first_ts:
            self.view_start = first_ts
            self.view_end = self.view_start + window_size

        # Disengage following mode - user is looking at history
        self.following = False
        self.update_plots()

    def action_pan_right(self):
        """Pan view right (forward in time). Re-engages following if we reach 'now'."""
        if not self.all_data or not self.view_start or not self.view_end:
            return

        window_size = self.view_end - self.view_start
        shift = timedelta(seconds=window_size.total_seconds() * 0.02)  # 2% of window

        self.view_start += shift
        self.view_end += shift

        last_ts = self.all_data[-1]['_ts']
        if self.view_end >= last_ts:
            # We've reached "now" - re-engage following mode
            self.view_end = last_ts
            self.view_start = self.view_end - window_size
            self.following = True

        self.update_plots()

    def action_zoom_in(self):
        """Zoom in (show less time). Keeps view anchored to 'now' if following."""
        if not self.view_start or not self.view_end:
            return

        window_size = self.view_end - self.view_start
        new_window = timedelta(seconds=window_size.total_seconds() * 0.5)

        if new_window.total_seconds() < 5:
            return

        if self.following and self.all_data:
            # Keep anchored to the latest data point
            last_ts = self.all_data[-1]['_ts']
            self.view_end = last_ts
            self.view_start = self.view_end - new_window
        else:
            # Zoom around center
            center = self.view_start + window_size / 2
            self.view_start = center - new_window / 2
            self.view_end = center + new_window / 2

        self.update_plots()

    def action_zoom_out(self):
        """Zoom out (show more time). Keeps view anchored to 'now' if following."""
        if not self.view_start or not self.view_end:
            return

        window_size = self.view_end - self.view_start
        new_window = timedelta(seconds=window_size.total_seconds() * 2.0)

        if self.following and self.all_data:
            # Keep anchored to the latest data point
            last_ts = self.all_data[-1]['_ts']
            self.view_end = last_ts
            self.view_start = self.view_end - new_window
        else:
            # Zoom around center
            center = self.view_start + window_size / 2
            self.view_start = center - new_window / 2
            self.view_end = center + new_window / 2

        # Clamp to data bounds
        if self.all_data:
            first_ts = self.all_data[0]['_ts']
            last_ts = self.all_data[-1]['_ts']

            if self.view_start < first_ts:
                self.view_start = first_ts

            if self.view_end > last_ts:
                self.view_end = last_ts

        self.update_plots()

    def action_jump_start(self):
        """Jump to start of data. Disengages following mode."""
        if not self.all_data:
            return

        first_ts = self.all_data[0]['_ts']

        window_size = self.view_end - self.view_start
        self.view_start = first_ts
        self.view_end = self.view_start + window_size

        # Disengage following - user wants to look at history
        self.following = False
        self.update_plots()

    def action_jump_end(self):
        """Jump to end of data. Re-engages following mode."""
        self.jump_end()

    def jump_end(self):
        """Jump to end of data (helper method). Re-engages following mode."""
        if not self.all_data:
            return

        last_ts = self.all_data[-1]['_ts']

        window_size = self.view_end - self.view_start
        self.view_end = last_ts
        self.view_start = self.view_end - window_size

        # Re-engage following - user wants to see "now"
        self.following = True
        self.update_plots()

    def action_reset_view(self):
        """Reset to default 60s view. Re-engages following mode."""
        self.reset_view()
        # Re-engage following - reset means back to live view
        self.following = True
        self.update_plots()

    def action_toggle_pause(self):
        """Toggle pause state for live updates."""
        if self.live_mode:
            self.paused = not self.paused
            self.update_plots()

    def action_scroll_down(self):
        """Scroll down (vim j)."""
        if self._scroll_container:
            self._scroll_container.scroll_relative(y=15, animate=False)

    def action_scroll_up(self):
        """Scroll up (vim k)."""
        if self._scroll_container:
            self._scroll_container.scroll_relative(y=-15, animate=False)

    def action_page_down(self):
        """Scroll down half page (vim Ctrl+d)."""
        if self._scroll_container:
            self._scroll_container.scroll_relative(y=self._scroll_container.size.height // 2, animate=False)

    def action_page_up(self):
        """Scroll up half page (vim Ctrl+u)."""
        if self._scroll_container:
            self._scroll_container.scroll_relative(y=-self._scroll_container.size.height // 2, animate=False)

    def action_scroll_top(self):
        """Scroll to top (vim g)."""
        if self._scroll_container:
            self._scroll_container.scroll_home(animate=False)

    def action_scroll_bottom(self):
        """Scroll to bottom (vim G)."""
        if self._scroll_container:
            self._scroll_container.scroll_end(animate=False)
