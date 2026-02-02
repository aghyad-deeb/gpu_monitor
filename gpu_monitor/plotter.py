"""High-fidelity plotting with Braille patterns for terminal display.

Inspired by btop's beautiful graph rendering using Unicode Braille patterns
for much higher resolution than traditional block characters.
"""

from rich.text import Text
from datetime import datetime, timedelta


# Braille patterns for high-resolution graphing
# Each braille character is a 2x4 dot matrix, giving us 8 levels per character width
# and 4 levels per character height - much better than block characters!
BRAILLE_OFFSET = 0x2800
BRAILLE_MAP = [
    [0x01, 0x08],  # Row 0: dots 1, 4
    [0x02, 0x10],  # Row 1: dots 2, 5
    [0x04, 0x20],  # Row 2: dots 3, 6
    [0x40, 0x80],  # Row 3: dots 7, 8
]


def create_braille_graph(values, width, height, color="cyan", filled=True, per_column_color=False, raw_values=None, value_max=100, return_lines=False):
    """
    Create a high-resolution graph using Braille patterns.

    Each character cell represents 2 data points horizontally and 4 vertical levels.
    This gives us 2x the horizontal resolution and 4x the vertical resolution
    compared to traditional block characters.

    Args:
        values: List of numeric values to plot
        width: Width in characters
        height: Height in characters
        color: Color for the graph (used if per_column_color=False)
        filled: If True, fill area under line; if False, draw only line
        per_column_color: If True, color each column based on its value
        raw_values: Original values for coloring (before normalization)
        value_max: Maximum value for color scaling (e.g., 100 for percentage, 80 for GB)
        return_lines: If True, return list of Text objects (one per line) instead of single Text
    """
    if not values or width < 1 or height < 1:
        return Text("No data", style="dim")

    # Normalize values to 0-1 range for plotting
    min_val = min(values)
    max_val = max(values)
    val_range = max_val - min_val if max_val != min_val else 1
    normalized = [(v - min_val) / val_range for v in values]

    # Keep raw values for coloring (use original values if provided)
    color_values = raw_values if raw_values is not None else values

    # Resample to fit width (2 data points per braille character)
    target_points = width * 2
    if len(normalized) > target_points:
        step = len(normalized) / target_points
        normalized = [normalized[int(i * step)] for i in range(target_points)]
        color_values = [color_values[int(i * step)] for i in range(target_points)]
    elif len(normalized) < target_points:
        # Pad with first value at the beginning (older data)
        padding_n = [normalized[0]] * (target_points - len(normalized))
        padding_c = [color_values[0]] * (target_points - len(color_values))
        normalized = padding_n + normalized
        color_values = padding_c + color_values

    # Total vertical dots = height * 4 (4 dots per braille row)
    total_dots_v = height * 4

    # Build the graph row by row (top to bottom)
    # Store both characters and their colors
    grid = []  # grid[row][col] = (char_code, color)

    for row in range(height):
        row_data = []
        for col in range(width):
            char_code = BRAILLE_OFFSET

            # Get 2 data points for this character
            idx1 = col * 2
            idx2 = col * 2 + 1

            v1 = normalized[idx1] if idx1 < len(normalized) else 0
            v2 = normalized[idx2] if idx2 < len(normalized) else 0

            # Convert normalized values to dot positions (0 = bottom, total_dots_v-1 = top)
            dot_y1 = int(v1 * (total_dots_v - 1))
            dot_y2 = int(v2 * (total_dots_v - 1))

            # Check each of the 4 dot rows in this character row
            for dot_row in range(4):
                # Calculate the actual dot position from top (row 0 = top)
                dot_pos = (height - 1 - row) * 4 + (3 - dot_row)

                if filled:
                    # Filled mode: light up all dots at or below the line
                    if dot_pos <= dot_y1:
                        char_code |= BRAILLE_MAP[dot_row][0]
                    if dot_pos <= dot_y2:
                        char_code |= BRAILLE_MAP[dot_row][1]
                else:
                    # Line mode: only light up dots on the line
                    if dot_pos == dot_y1 or (dot_row < 3 and dot_pos < dot_y1 and (height - 1 - row) * 4 + (3 - dot_row - 1) > dot_y1):
                        char_code |= BRAILLE_MAP[dot_row][0]
                    if dot_pos == dot_y2 or (dot_row < 3 and dot_pos < dot_y2 and (height - 1 - row) * 4 + (3 - dot_row - 1) > dot_y2):
                        char_code |= BRAILLE_MAP[dot_row][1]

            # Determine color for this column based on actual value (not normalized)
            if per_column_color:
                c1 = color_values[idx1] if idx1 < len(color_values) else 0
                c2 = color_values[idx2] if idx2 < len(color_values) else 0
                avg_raw = (c1 + c2) / 2
                # Scale to 0-1 range based on value_max
                scaled = min(avg_raw / value_max, 1.0)
                col_color = get_gradient_color(scaled)
            else:
                col_color = color

            row_data.append((chr(char_code), col_color))

        grid.append(row_data)

    if return_lines:
        # Return list of Text objects, one per line
        lines = []
        for row_data in grid:
            line_text = Text()
            for char, col_color in row_data:
                line_text.append(char, style=col_color)
            lines.append(line_text)
        return lines
    else:
        # Return single Text with newlines
        text = Text()
        for i, row_data in enumerate(grid):
            for char, col_color in row_data:
                text.append(char, style=col_color)
            if i < len(grid) - 1:
                text.append("\n")
        return text


def get_gradient_color(value, low_color="green", mid_color="yellow", high_color="red"):
    """Get color based on value (0-1 range)."""
    if value < 0.5:
        return low_color
    elif value < 0.75:
        return mid_color
    else:
        return high_color


def create_sparkline(values, width=20, color="cyan"):
    """Create a compact sparkline using block characters."""
    if not values:
        return Text("─" * width, style="dim")

    blocks = " ▁▂▃▄▅▆▇█"
    min_val = min(values)
    max_val = max(values)
    val_range = max_val - min_val if max_val != min_val else 1

    # Resample to width
    if len(values) > width:
        step = len(values) / width
        values = [values[int(i * step)] for i in range(width)]

    spark = []
    for v in values:
        normalized = (v - min_val) / val_range
        idx = min(int(normalized * (len(blocks) - 1)), len(blocks) - 1)
        spark.append(blocks[idx])

    # Pad if needed
    while len(spark) < width:
        spark.insert(0, blocks[0])

    return Text(''.join(spark), style=color)


def create_progress_bar(value, max_value, width=20, show_percent=True):
    """Create a beautiful gradient progress bar."""
    if max_value <= 0:
        return Text("─" * width, style="dim")

    percent = min(value / max_value, 1.0)
    filled = int(width * percent)

    # Gradient colors based on percentage
    if percent < 0.5:
        filled_color = "green"
        text_color = "bold green"
    elif percent < 0.75:
        filled_color = "yellow"
        text_color = "bold yellow"
    else:
        filled_color = "red"
        text_color = "bold red"

    text = Text()
    # Filled portion with gradient effect
    text.append("█" * filled, style=filled_color)
    # Empty portion - use a visible gray
    text.append("░" * (width - filled), style="#4a4a4a")

    if show_percent:
        text.append(f" {percent*100:5.1f}%", style=text_color)

    return text


class AxisPlot:
    """Creates a beautiful plot with labeled axes using Braille patterns."""

    def __init__(self, width=50, height=6):
        self.width = width
        self.height = height
        self.y_axis_width = 7
        self.plot_width = width - self.y_axis_width - 1

    def render(self, values, timestamps, y_label, y_unit, min_val=None, max_val=None,
               color="cyan", process_names=None, color_max=100):
        """Render a beautiful plot with axes."""
        if not values:
            return Text("  No data available", style="dim")

        # Calculate value range
        if min_val is None:
            min_val = min(values)
        if max_val is None:
            max_val = max(values)

        value_range = max_val - min_val
        if value_range == 0:
            value_range = 1
            max_val = min_val + 1

        # Current and average values
        current_val = values[-1]
        avg_val = sum(values) / len(values)

        # Color based on value level
        level = (current_val - min_val) / value_range if value_range > 0 else 0
        value_color = get_gradient_color(level)

        text = Text()

        # Title line with current value
        text.append(f"  {y_label}", style="bold")
        text.append(f" {current_val:.1f}", style=f"bold {value_color}")
        text.append(f"{y_unit}", style=value_color)
        text.append(f"  avg:", style="dim")
        text.append(f"{avg_val:.1f}{y_unit}", style="dim")
        text.append("\n")

        # Top border with max value
        if y_unit == "GB":
            max_label = f"{max_val:5.1f}"
        else:
            max_label = f"{max_val:5.0f}"
        text.append(f" {max_label}│", style="dim")
        text.append("┌" + "─" * self.plot_width + "┐", style="#6e7681")
        text.append("\n")

        # Create braille graph with per-column coloring based on actual values
        # Use return_lines=True to get a list of Text objects with colors preserved
        graph_lines = create_braille_graph(
            values, self.plot_width, self.height - 2, color,
            per_column_color=True, raw_values=values, value_max=color_max,
            return_lines=True
        )

        for i, line_text in enumerate(graph_lines):
            # Y-axis label (only at certain positions)
            if i == len(graph_lines) // 2:
                mid_val = (max_val + min_val) / 2
                if y_unit == "GB":
                    text.append(f"{mid_val:6.1f}│", style="dim")
                else:
                    text.append(f"{mid_val:6.0f}│", style="dim")
            else:
                text.append("      │", style="dim")

            text.append_text(line_text)
            text.append("│", style="#6e7681")
            text.append("\n")

        # Bottom border with min value
        if y_unit == "GB":
            min_label = f"{min_val:5.1f}"
        else:
            min_label = f"{min_val:5.0f}"
        text.append(f" {min_label}│", style="dim")
        text.append("└" + "─" * self.plot_width + "┘", style="#6e7681")
        text.append("\n")

        # X-axis time labels
        if timestamps:
            start_time = timestamps[0]
            end_time = timestamps[-1]

            if isinstance(start_time, datetime) and isinstance(end_time, datetime):
                start_str = start_time.strftime("%H:%M:%S")
                end_str = end_time.strftime("%H:%M:%S")
            else:
                start_str = "start"
                end_str = "end"

            # Format: "       HH:MM:SS                        HH:MM:SS"
            padding = " " * self.y_axis_width
            time_line = f"{padding} {start_str}"
            gap = self.plot_width - len(start_str) - len(end_str)
            if gap > 0:
                time_line += " " * gap
            time_line += end_str
            text.append(time_line, style="dim")
            text.append("\n")

        # Process info (if available)
        if process_names:
            unique_procs = []
            for proc in process_names:
                if proc and proc not in unique_procs:
                    unique_procs.append(proc)

            if unique_procs:
                proc_str = unique_procs[-1]  # Show most recent
                if len(proc_str) > self.width - 10:
                    proc_str = proc_str[:self.width - 13] + "..."
                text.append(f"       ⚙ ", style="dim")
                text.append(proc_str, style="italic magenta")
                text.append("\n")

        return text


def create_plot(values, timestamps, metric_name, y_label, y_unit, width=50, height=6, process_names=None):
    """Create a beautiful high-resolution plot."""
    if not values:
        return Text("  No data", style="dim")

    # Color thresholds based on metric type
    avg = sum(values) / len(values)

    if metric_name == "util":
        color = get_gradient_color(avg / 100)
        min_val, max_val = 0, 100
        color_max = 100  # 0-100%
    elif metric_name == "mem":
        # Memory in GB - assume 80GB max for coloring
        color = get_gradient_color(avg / 80)
        min_val = None
        max_val = None
        color_max = 80  # GB
    elif metric_name == "temp":
        # Temperature - 30C is green, 90C is red
        color = get_gradient_color((avg - 30) / 60)
        min_val = None
        max_val = None
        color_max = 90  # Celsius (but scaled from 30)
    elif metric_name == "power":
        color = get_gradient_color(avg / 400)
        min_val = None
        max_val = None
        color_max = 400  # Watts
    else:
        color = "cyan"
        min_val = None
        max_val = None
        color_max = 100

    plotter = AxisPlot(width=width, height=height)
    return plotter.render(values, timestamps, y_label, y_unit, min_val, max_val, color, process_names, color_max)
