from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Label
from textual.containers import Container, Vertical, Horizontal, Grid
from textual import events
from textual.reactive import reactive
from rich.text import Text
from rich.style import Style
import time
from datetime import datetime, timedelta
from pathlib import Path

from .utils import parse_log_file, format_timestamp, parse_timestamp
from .plotter import create_plot


class Sparkline(Static):
    """A compact sparkline chart widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.values = []
        self.color = "cyan"

    def update_values(self, values, color="cyan"):
        """Update sparkline with new values."""
        self.values = values[-60:] if len(values) > 60 else values  # Keep last 60 points
        self.color = color
        self.refresh()

    def render(self) -> Text:
        """Render sparkline using block characters."""
        if not self.values:
            return Text("" * 30, style=f"dim")

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

        # Color based on percentage
        if percentage < 0.5:
            color = "green"
        elif percentage < 0.75:
            color = "yellow"
        else:
            color = "red"

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
        text.append(f"{self.label:8s} ", style="bold cyan")
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
            text.append(f"  GPU {self.gpu_id}", style="bold cyan")
            text.append(" │ ", style="bright_black")
            text.append("Waiting for data...", style="dim italic")
            return text

        metrics = self.metrics

        # ═══════════════════════════════════════════════════════════
        # HEADER: GPU ID + Status
        # ═══════════════════════════════════════════════════════════
        util = metrics['utilization_gpu']

        # Status indicator with icon
        if util > 80:
            status_icon = "●"
            status_color = "red"
            status_text = "HIGH"
        elif util > 30:
            status_icon = "●"
            status_color = "yellow"
            status_text = "ACTIVE"
        else:
            status_icon = "●"
            status_color = "green"
            status_text = "IDLE"

        text.append(f" GPU {self.gpu_id}", style="bold white")
        text.append(" │ ", style="bright_black")
        text.append(f"{status_icon} ", style=f"bold {status_color}")
        text.append(f"{status_text}", style=f"{status_color}")
        text.append("\n")

        # Process info on its own row
        process_info = metrics.get('process_info', '')
        if process_info:
            text.append(" ⚙ ", style="dim")
            text.append(f"{process_info}", style="magenta")
            text.append("\n")

        # ═══════════════════════════════════════════════════════════
        # METRICS BAR: Compact view of all metrics with progress bars
        # ═══════════════════════════════════════════════════════════
        mem_used = metrics['memory_used'] / 1024
        mem_total = metrics['memory_total'] / 1024
        temp = metrics['temperature']
        power = metrics['power_draw']

        # GPU and Memory on same line (smaller bars)
        text.append(" GPU ", style="dim")
        text.append_text(create_progress_bar(util, 100, width=8, show_percent=False))
        text.append(f"{util:4.0f}%", style="bold " + ("red" if util > 80 else ("yellow" if util > 30 else "green")))

        text.append(" │ ", style="bright_black")
        text.append("MEM ", style="dim")
        mem_pct = (mem_used / mem_total * 100) if mem_total > 0 else 0
        text.append_text(create_progress_bar(mem_used, mem_total, width=8, show_percent=False))
        text.append(f"{mem_used:4.0f}G", style="bold " + ("red" if mem_pct > 80 else ("yellow" if mem_pct > 60 else "green")))

        text.append("\n")

        # Temperature and Power on second line (smaller bars)
        text.append(" TMP ", style="dim")
        text.append_text(create_progress_bar(temp, 100, width=8, show_percent=False))
        temp_color = "red" if temp > 80 else ("yellow" if temp > 65 else "green")
        text.append(f"{temp:4.0f}°", style=f"bold {temp_color}")

        text.append(" │ ", style="bright_black")
        text.append("PWR ", style="dim")
        text.append_text(create_progress_bar(power, 400, width=8, show_percent=False))
        power_color = "red" if power > 300 else ("yellow" if power > 200 else "green")
        text.append(f"{power:4.0f}W", style=f"bold {power_color}")

        text.append("\n")

        # ═══════════════════════════════════════════════════════════
        # GRAPH: High-resolution Braille plot
        # ═══════════════════════════════════════════════════════════
        if self.history:
            timestamps = [parse_timestamp(p['timestamp']) for p in self.history]
            process_names = [p.get('process_info', '') for p in self.history]

            text.append(" ─────────────────────────────────────────────────────\n", style="#6e7681")

            if self.show_gpu:
                util_values = [p['utilization_gpu'] for p in self.history]
                plot_text = create_plot(util_values, timestamps, "util", "GPU", "%",
                                       width=54, height=10, process_names=process_names)
                text.append_text(plot_text)

            if self.show_mem:
                mem_values = [p['memory_used'] / 1024 for p in self.history]
                plot_text = create_plot(mem_values, timestamps, "mem", "MEM", "GB",
                                       width=54, height=10, process_names=process_names)
                text.append_text(plot_text)

            if self.show_temp:
                temp_values = [p['temperature'] for p in self.history]
                plot_text = create_plot(temp_values, timestamps, "temp", "TMP", "°C",
                                       width=54, height=10, process_names=process_names)
                text.append_text(plot_text)

            if self.show_power:
                power_values = [p['power_draw'] for p in self.history]
                plot_text = create_plot(power_values, timestamps, "power", "PWR", "W",
                                       width=54, height=10, process_names=process_names)
                text.append_text(plot_text)

        return text


class GPUMonitorApp(App):
    """Main Textual application for GPU monitoring with enhanced aesthetics."""

    CSS = """
    Screen {
        background: #0d1117;
    }

    Header {
        background: #161b22;
        color: #c9d1d9;
        text-style: bold;
        height: 1;
    }

    Footer {
        background: #161b22;
        height: 1;
    }

    #main-container {
        height: 100%;
        padding: 0;
        background: #0d1117;
    }

    #title-bar {
        height: 3;
        background: #161b22;
        color: #58a6ff;
        content-align: center middle;
        text-style: bold;
        border: solid #58a6ff;
        margin: 0 1 1 1;
    }

    #gpu-grid {
        height: auto;
        layout: grid;
        grid-size: 2;
        grid-gutter: 1 2;
        padding: 0 1;
    }

    GPUCard {
        height: auto;
        min-height: 24;
        min-width: 60;
        background: #161b22;
        border: solid #6e7681;
        padding: 1 1;
    }

    GPUCard:hover {
        border: solid #58a6ff;
    }

    #controls {
        dock: bottom;
        height: 2;
        background: #161b22;
        color: #8b949e;
        content-align: center middle;
        border-top: solid #6e7681;
    }

    .status-bar {
        background: #161b22;
        height: auto;
        padding: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("left,h", "pan_left", "← Pan"),
        ("right,l", "pan_right", "Pan →"),
        ("minus,j", "zoom_out", "- Zoom"),
        ("plus,k", "zoom_in", "+ Zoom"),
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
        self.view_start = None
        self.view_end = None
        self.default_window = 300  # 5 minutes
        self.last_update = 0
        self.update_interval = 1.0
        self.gpu_ids = []
        # following = True means view auto-scrolls with new data
        # following = False means view stays fixed (user panned away from "now")
        self.following = True

    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Header()

        with Vertical(id="main-container"):
            yield Static("", id="title-bar")

            with Grid(id="gpu-grid"):
                # GPU cards will be added dynamically
                pass

        yield Static("", id="controls")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize when app is mounted."""
        self.title = "GPU Monitor"
        self.load_data()

        # Detect GPUs
        if self.all_data:
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

        # Delay initial update to ensure widgets are fully mounted
        self.set_timer(0.1, self.update_plots)

        if self.live_mode:
            self.set_interval(self.update_interval, self.update_live_data)

    def update_title(self):
        """Update title bar with file info."""
        title_text = Text()

        # Clean, minimal title
        title_text.append("  ◈ ", style="bold #58a6ff")
        title_text.append("GPU Monitor", style="bold white")
        title_text.append("  │  ", style="#30363d")
        title_text.append(f"{len(self.gpu_ids)}", style="bold #7ee787")
        title_text.append(" GPUs", style="#7ee787")
        title_text.append("  │  ", style="#30363d")
        title_text.append(f"{self.log_file.name}", style="#8b949e")

        if self.live_mode:
            title_text.append("  │  ", style="#30363d")
            title_text.append("● ", style="bold #f85149")
            title_text.append("LIVE", style="#f85149")

        title_bar = self.query_one("#title-bar", Static)
        title_bar.update(title_text)

    def load_data(self):
        """Load data from log file."""
        try:
            self.all_data = parse_log_file(self.log_file)
        except Exception as e:
            self.all_data = []

    def update_live_data(self):
        """Periodically reload data in live mode."""
        if not self.paused and self.live_mode:
            self.load_data()

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
                last_ts = parse_timestamp(self.all_data[-1]['timestamp'])
                if last_ts:
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
            last_ts = parse_timestamp(self.all_data[-1]['timestamp'])
            if last_ts:
                self.view_end = last_ts
                self.view_start = self.view_end - timedelta(seconds=self.default_window)
            else:
                self.view_start = datetime.now() - timedelta(seconds=self.default_window)
                self.view_end = datetime.now()

        # Don't call update_plots here - let caller handle it
        # to avoid updating before widgets are mounted

    def get_visible_data(self):
        """Get data within the current view window."""
        if not self.all_data or not self.view_start or not self.view_end:
            return []

        visible = []
        for point in self.all_data:
            ts = parse_timestamp(point['timestamp'])
            if ts and self.view_start <= ts <= self.view_end:
                visible.append(point)

        return visible

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

        controls_text = Text()
        controls_text.append("  ", style="")
        controls_text.append(f"{self.view_start.strftime('%H:%M:%S')}", style="#8b949e")
        controls_text.append(" → ", style="#30363d")
        controls_text.append(f"{self.view_end.strftime('%H:%M:%S')}", style="#8b949e")
        controls_text.append(f"  {window_sec:.0f}s", style="#58a6ff")

        controls_text.append("  │  ", style="#30363d")

        if self.paused:
            controls_text.append("▐▐ ", style="#f85149")
            controls_text.append("PAUSED", style="#f85149")
        elif self.live_mode and self.following:
            controls_text.append("● ", style="#7ee787")
            controls_text.append("LIVE", style="#7ee787")
        elif self.live_mode and not self.following:
            controls_text.append("◆ ", style="#f0883e")
            controls_text.append("HISTORY", style="#f0883e")
        else:
            controls_text.append("◼ ", style="#58a6ff")
            controls_text.append("STATIC", style="#58a6ff")

        controls_text.append("  │  ", style="#30363d")
        controls_text.append(f"{len(visible_data)} samples", style="#8b949e")

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

        first_ts = parse_timestamp(self.all_data[0]['timestamp'])
        if first_ts and self.view_start < first_ts:
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

        last_ts = parse_timestamp(self.all_data[-1]['timestamp'])
        if last_ts and self.view_end >= last_ts:
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
            last_ts = parse_timestamp(self.all_data[-1]['timestamp'])
            if last_ts:
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
            last_ts = parse_timestamp(self.all_data[-1]['timestamp'])
            if last_ts:
                self.view_end = last_ts
                self.view_start = self.view_end - new_window
        else:
            # Zoom around center
            center = self.view_start + window_size / 2
            self.view_start = center - new_window / 2
            self.view_end = center + new_window / 2

        # Clamp to data bounds
        if self.all_data:
            first_ts = parse_timestamp(self.all_data[0]['timestamp'])
            last_ts = parse_timestamp(self.all_data[-1]['timestamp'])

            if first_ts and self.view_start < first_ts:
                self.view_start = first_ts

            if last_ts and self.view_end > last_ts:
                self.view_end = last_ts

        self.update_plots()

    def action_jump_start(self):
        """Jump to start of data. Disengages following mode."""
        if not self.all_data:
            return

        first_ts = parse_timestamp(self.all_data[0]['timestamp'])
        if not first_ts:
            return

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

        last_ts = parse_timestamp(self.all_data[-1]['timestamp'])
        if not last_ts:
            return

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
