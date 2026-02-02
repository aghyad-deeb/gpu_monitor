import argparse
import sys
import threading
import time
from pathlib import Path
from datetime import datetime

from .logger import GPULogger
from .visualizer import GPUMonitorApp
from .utils import find_logs, get_latest_log


def main():
    parser = argparse.ArgumentParser(
        description='GPU Monitor - Log and visualize NVIDIA GPU metrics'
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Log command
    log_parser = subparsers.add_parser('log', help='Start logging GPU metrics')
    log_parser.add_argument(
        '--interval',
        type=float,
        default=1.0,
        help='Sampling interval in seconds (default: 1.0)'
    )
    log_parser.add_argument(
        '--output',
        type=str,
        help='Output log file path (default: auto-generated in logs/)'
    )

    # View command
    view_parser = subparsers.add_parser('view', help='Visualize GPU log file')
    view_parser.add_argument(
        'logfile',
        nargs='?',
        help='Path to log file to visualize'
    )
    view_parser.add_argument(
        '--latest',
        action='store_true',
        help='Visualize the most recent log file'
    )
    view_parser.add_argument(
        '--show-gpu',
        action='store_true',
        help='Show GPU utilization plot'
    )
    view_parser.add_argument(
        '--show-temp',
        action='store_true',
        help='Show temperature plot'
    )
    view_parser.add_argument(
        '--show-power',
        action='store_true',
        help='Show power draw plot'
    )
    view_parser.add_argument(
        '--show-all',
        action='store_true',
        help='Show all metric plots'
    )

    # List command
    list_parser = subparsers.add_parser('list', help='List available log files')

    args = parser.parse_args()

    # Default behavior: run both logging and visualization
    if args.command is None:
        run_combined_mode()
    elif args.command == 'log':
        run_log_mode(args)
    elif args.command == 'view':
        run_view_mode(args)
    elif args.command == 'list':
        run_list_mode()


def run_combined_mode():
    """Run logging and visualization together in one command."""
    # Create log file path
    logs_dir = Path(__file__).parent.parent / 'logs'
    logs_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = logs_dir / f'gpu_{timestamp}.csv'

    # Create logger instance
    logger = GPULogger(log_file, interval=1.0)

    # Start logging in background thread
    stop_event = threading.Event()

    def logging_thread():
        try:
            logger.start_logging(stop_event)
        except Exception as e:
            print(f"Logging error: {e}", file=sys.stderr)

    log_thread = threading.Thread(target=logging_thread, daemon=True)
    log_thread.start()

    # Give logger time to write initial data
    time.sleep(1.5)

    # Run visualizer in main thread (default: memory only)
    try:
        app = GPUMonitorApp(log_file, live_mode=True,
                           show_gpu=False, show_mem=True, show_temp=False, show_power=False)
        app.run()
    finally:
        # Clean shutdown
        stop_event.set()
        log_thread.join(timeout=2.0)


def run_log_mode(args):
    """Run logging only."""
    if args.output:
        log_file = Path(args.output)
    else:
        logs_dir = Path(__file__).parent.parent / 'logs'
        logs_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = logs_dir / f'gpu_{timestamp}.csv'

    logger = GPULogger(log_file, interval=args.interval)
    stop_event = threading.Event()

    print(f"Starting GPU logging to: {log_file}")
    print(f"Sampling interval: {args.interval}s")
    print("Press Ctrl+C to stop")

    try:
        logger.start_logging(stop_event)
    except KeyboardInterrupt:
        print("\nStopping logging...")
        stop_event.set()


def run_view_mode(args):
    """Run visualization only."""
    if args.latest:
        log_file = get_latest_log()
        if not log_file:
            print("No log files found in logs/ directory", file=sys.stderr)
            sys.exit(1)
    elif args.logfile:
        log_file = Path(args.logfile)
        if not log_file.exists():
            print(f"Log file not found: {log_file}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Please specify a log file or use --latest", file=sys.stderr)
        sys.exit(1)

    # Determine which metrics to show
    show_all = args.show_all
    show_gpu = args.show_gpu or show_all
    show_mem = True  # Always show memory by default
    show_temp = args.show_temp or show_all
    show_power = args.show_power or show_all

    app = GPUMonitorApp(log_file, live_mode=False,
                       show_gpu=show_gpu, show_mem=show_mem,
                       show_temp=show_temp, show_power=show_power)
    app.run()


def run_list_mode():
    """List available log files."""
    logs = find_logs()

    if not logs:
        print("No log files found in logs/ directory")
        return

    print(f"Found {len(logs)} log file(s):\n")
    for log_file in logs:
        size = log_file.stat().st_size
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        print(f"  {log_file.name}")
        print(f"    Size: {size:,} bytes")
        print(f"    Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
