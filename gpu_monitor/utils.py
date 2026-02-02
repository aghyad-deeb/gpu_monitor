import csv
from pathlib import Path
from datetime import datetime


def find_logs(logs_dir=None):
    """Find all GPU log files in the logs directory."""
    if logs_dir is None:
        logs_dir = Path(__file__).parent.parent / 'logs'
    else:
        logs_dir = Path(logs_dir)

    if not logs_dir.exists():
        return []

    # Find all CSV files matching the pattern
    log_files = sorted(logs_dir.glob('gpu_*.csv'), key=lambda p: p.stat().st_mtime)
    return log_files


def get_latest_log(logs_dir=None):
    """Get the most recently modified log file."""
    logs = find_logs(logs_dir)
    return logs[-1] if logs else None


def parse_log_file(log_path):
    """Parse a GPU log CSV file into structured data.

    Returns a list of dicts with parsed data.
    """
    log_path = Path(log_path)

    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")

    data = []

    with open(log_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Convert numeric values
                parsed_row = {
                    'timestamp': row['timestamp'],
                    'gpu_id': int(row['gpu_id']),
                    'utilization_gpu': float(row['utilization_gpu']),
                    'memory_used': float(row['memory_used']),
                    'memory_total': float(row['memory_total']),
                    'temperature': float(row['temperature']),
                    'power_draw': float(row['power_draw']) if row['power_draw'] else 0.0,
                    'process_info': row.get('process_info', '')  # Backward compatible
                }
                data.append(parsed_row)
            except (ValueError, KeyError) as e:
                # Skip malformed rows
                continue

    return data


def format_timestamp(ts_str):
    """Format timestamp string for display."""
    try:
        # Try parsing nvidia-smi timestamp format
        dt = datetime.strptime(ts_str, '%Y/%m/%d %H:%M:%S.%f')
        return dt.strftime('%H:%M:%S')
    except ValueError:
        # Fallback to raw string
        return ts_str


def parse_timestamp(ts_str):
    """Parse timestamp string to datetime object."""
    try:
        return datetime.strptime(ts_str, '%Y/%m/%d %H:%M:%S.%f')
    except ValueError:
        # Try without microseconds
        try:
            return datetime.strptime(ts_str, '%Y/%m/%d %H:%M:%S')
        except ValueError:
            return None
