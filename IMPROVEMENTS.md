# GPU Monitor - Multi-GPU & Aesthetic Improvements

## New Features Implemented

### 1. Multi-GPU Display
- **All GPUs displayed simultaneously** in a responsive grid layout
- Automatically detects and shows all available GPUs (tested with 8 GPUs)
- 2-column grid layout for optimal space utilization

### 2. Enhanced Visual Design

#### GPU Cards
- Individual card per GPU with rounded borders
- Status indicators:
  - 🔥 HOT (>80% utilization) - Red
  - ⚡ ACTIVE (30-80% utilization) - Yellow
  - 💤 IDLE (<30% utilization) - Green

#### Metric Bars
- **Color-coded progress bars** for each metric:
  - Green (< 50%) - Safe
  - Yellow (50-75%) - Moderate
  - Red (> 75%) - High
- Metrics displayed:
  - GPU Utilization (%)
  - Memory Usage (GB with total)
  - Temperature (°C)
  - Power Draw (W)

#### Sparklines
- **Historical usage sparklines** showing last 40 data points
- Color-coded based on average utilization
- Uses 8-level block characters (▁▂▃▄▅▆▇█) for smooth visualization

### 3. Enhanced Title Bar
- Unicode box drawing characters for borders
- Shows:
  - File name being visualized
  - Number of GPUs detected
  - Live mode indicator (🔴 LIVE)

### 4. Improved Status Bar
- Time window display with arrow (→)
- Mode indicators:
  - ▶ LIVE (green) - Active real-time monitoring
  - ⏹ STATIC (blue) - Viewing recorded data
  - ⏸ PAUSED (yellow) - Paused live mode
- Sample count display

### 5. Better Controls Display
- Symbol-based shortcuts in footer
- Clearer navigation indicators

## Visual Comparison

### Before
- Single GPU display only
- Basic ASCII bars
- Minimal styling
- No status indicators

### After
- ✅ All 8 GPUs visible at once
- ✅ Rich color-coded bars (green/yellow/red)
- ✅ Status emojis and indicators
- ✅ Sparklines for historical context
- ✅ Professional borders and layout
- ✅ Real-time status badges
- ✅ Better information density

## Technical Improvements

1. **Rich Text Rendering**: Using Rich library for colored, styled text
2. **Grid Layout**: Responsive 2-column grid using Textual's Grid container
3. **Dynamic GPU Detection**: Auto-discovers and displays all GPUs
4. **Modular Components**:
   - `GPUCard` - Self-contained GPU display
   - `MetricBar` - Reusable progress bar widget
   - `Sparkline` - Historical data visualization

## Usage

All modes work identically:
```bash
cd ~/gpu-monitor

# View all GPUs in real-time
./gpu-monitor

# View latest log with all GPUs
./gpu-monitor view --latest

# List all logs
./gpu-monitor list
```

## Color Scheme

- Primary: Cyan accents and borders
- Status Colors:
  - Green: Safe/idle states
  - Yellow: Moderate/active states
  - Red: High/critical states
  - Blue: Info/static states

