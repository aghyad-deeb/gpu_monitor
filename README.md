# GPU Monitor

A beautiful terminal-based GPU monitoring tool that logs nvidia-smi data and provides an interactive visualization with multi-GPU support and enhanced aesthetics.

## ✨ Features

- **Multi-GPU Display**: All GPUs visible simultaneously in a 2-column grid
- **Process Tracking**: See which processes/functions are running on each GPU (e.g., "ray::function_name")
- **Color-Coded Metrics**: Green/yellow/red progress bars based on thresholds
- **Status Indicators**: 🔥 HOT | ⚡ ACTIVE | 💤 IDLE with emoji indicators
- **Time-Series Graphs**: Historical usage plots with labeled axes (matplotlib-style)
- **Process Timeline**: See which processes were running at different times on the graph
- **Real-time Monitoring**: Live updates with color-coded status badges
- **Time Navigation**: Pan, zoom, and jump through historical data
- **Professional UI**: Unicode borders, rich colors, and clean layout
- **CSV Logging**: Easy data export and analysis

## Installation

```bash
cd gpu-monitor
pip install -r requirements.txt
chmod +x gpu-monitor
```

## Requirements

- Python 3.8+
- NVIDIA GPU with nvidia-smi
- NVIDIA drivers installed
- psutil (for process information - automatically installed)

## Usage

### Default Mode: Logging + Visualization

Start both logging and visualization together:

```bash
./gpu-monitor
```

This creates a new log file in `logs/` and opens the interactive viewer. Press Ctrl+C to stop.

### Log Only Mode

Run logging in the background:

```bash
./gpu-monitor log
```

Optional arguments:
- `--interval <seconds>`: Sampling interval (default: 1.0)
- `--output <path>`: Custom output file path

### View Mode

Visualize an existing log file:

```bash
# View most recent log (memory only by default)
./gpu-monitor view --latest

# Add GPU utilization
./gpu-monitor view --latest --show-gpu

# Add temperature monitoring
./gpu-monitor view --latest --show-temp

# Add power draw
./gpu-monitor view --latest --show-power

# Show all metrics
./gpu-monitor view --latest --show-all

# View specific log file
./gpu-monitor view logs/gpu_20260202_143052.csv --show-all
```

**Note:** By default, only **memory usage** is plotted (to reduce clutter), but **all metrics are logged and current statistics for all metrics are always displayed** in each GPU card header. Use flags to show additional plots.

### List Logs

List all available log files:

```bash
./gpu-monitor list
```

## Keyboard Controls

When viewing logs in the interactive UI:

| Key | Action |
|-----|--------|
| `←` / `h` | Pan left (back in time) |
| `→` / `l` | Pan right (forward in time) |
| `-` / `j` | Zoom out (show more time) |
| `+` / `k` | Zoom in (show less time) |
| `Home` | Jump to start of data |
| `End` | Jump to end of data |
| `r` | Reset to default view (last 60s) |
| `Space` | Pause/resume live updates |
| `q` | Quit |

## Log File Format

Logs are stored as CSV files in the `logs/` directory with the naming pattern:

```
gpu_YYYYMMDD_HHMMSS.csv
```

CSV columns:
- `timestamp`: Time of measurement
- `gpu_id`: GPU index (0, 1, 2, ...)
- `utilization_gpu`: GPU utilization percentage (0-100)
- `memory_used`: GPU memory used (MB)
- `memory_total`: Total GPU memory (MB)
- `temperature`: GPU temperature (°C)
- `power_draw`: Power consumption (W)
- `process_info`: Active process/function name (e.g., "ray::train_model")

## 📊 Visualization Features

The interactive UI displays **all GPUs simultaneously** in a responsive grid with:

### Per-GPU Metrics
1. **Process Information**: Current process/function running on the GPU
2. **GPU Utilization (%)**: Current value with color coding
3. **Memory Usage (GB)**: Current used/total with dynamic threshold colors
4. **Temperature (°C)**: Current thermal reading with color indicators
5. **Power Draw (W)**: Current power consumption tracking

### Visual Enhancements
- **Status Badges**: 🔥 HOT (>80%) | ⚡ ACTIVE (30-80%) | 💤 IDLE (<30%)
- **Process Timeline**: Shows which processes ran during the visible time window
- **Labeled Axes**: Y-axis with value labels, X-axis with time labels
- **Color Coding**: Automatic threshold-based coloring
- **Unicode Borders**: Professional box-drawing characters
- **Live Indicators**: Real-time status with ▶ LIVE | ⏹ STATIC | ⏸ PAUSED

## 🎮 Multi-GPU Support

**All GPUs displayed at once!** The tool automatically detects all available NVIDIA GPUs and shows them in a clean 2-column grid layout. Perfect for monitoring multi-GPU training or inference workloads.

## Examples

### Quick monitoring session

```bash
# Start monitoring in one command
./gpu-monitor

# Use arrow keys to navigate through time
# Press 'q' to quit
```

### Background logging for later analysis

```bash
# Start logging in background
./gpu-monitor log &

# Do your GPU work...
python train_model.py

# Stop logging
pkill -f "gpu-monitor log"

# View the recorded data
./gpu-monitor view --latest
```

### Custom logging interval

```bash
# Sample every 0.5 seconds
./gpu-monitor log --interval 0.5
```

## Troubleshooting

### "nvidia-smi not found"

Make sure NVIDIA drivers are installed:
```bash
nvidia-smi
```

### Empty or no graphs

- Check that the log file has data: `cat logs/gpu_*.csv`
- Ensure nvidia-smi is working: `nvidia-smi`
- Try resetting the view with `r` key

### Terminal too small

The UI adapts to terminal size, but for best experience use at least 80x24 terminal.

## Future Enhancements

Potential features for future versions:
- Alerts/thresholds for high GPU usage or temperature
- Multi-GPU display in visualization
- Log file compression for old logs
- Export capabilities (PNG snapshots, CSV summaries)
- Remote monitoring (SSH to remote machine's logs)
- Configurable metrics and plot layouts

## License

MIT License
