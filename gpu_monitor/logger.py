import subprocess
import csv
import time
from pathlib import Path
from datetime import datetime
import re

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class GPULogger:
    """Logs NVIDIA GPU metrics to CSV file."""

    def __init__(self, output_file, interval=1.0):
        self.output_file = Path(output_file)
        self.interval = interval
        self.csv_headers = [
            'timestamp',
            'gpu_id',
            'utilization_gpu',
            'memory_used',
            'memory_total',
            'temperature',
            'power_draw',
            'process_info'
        ]
        self.gpu_uuid_map = None

    def query_nvidia_smi(self):
        """Query nvidia-smi for GPU metrics."""
        try:
            result = subprocess.run(
                [
                    'nvidia-smi',
                    '--query-gpu=timestamp,index,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw',
                    '--format=csv,noheader,nounits'
                ],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"nvidia-smi failed: {e.stderr}")
        except FileNotFoundError:
            raise RuntimeError("nvidia-smi not found. Is NVIDIA driver installed?")

    def build_gpu_uuid_map(self):
        """Build mapping from GPU UUID to GPU index."""
        try:
            result = subprocess.run(
                [
                    'nvidia-smi',
                    '--query-gpu=index,uuid',
                    '--format=csv,noheader'
                ],
                capture_output=True,
                text=True,
                check=True
            )

            gpu_map = {}
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 2:
                    gpu_map[parts[1]] = int(parts[0])

            return gpu_map
        except:
            return {}

    def get_gpu_processes(self):
        """Get process information for all GPUs."""
        if self.gpu_uuid_map is None:
            self.gpu_uuid_map = self.build_gpu_uuid_map()

        try:
            result = subprocess.run(
                [
                    'nvidia-smi',
                    '--query-compute-apps=pid,process_name,gpu_uuid',
                    '--format=csv,noheader,nounits'
                ],
                capture_output=True,
                text=True,
                check=True
            )

            gpu_processes = {}  # gpu_id -> process_info

            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue

                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 3:
                    pid = int(parts[0])
                    process_name = parts[1]
                    gpu_uuid = parts[2]
                    gpu_id = self.gpu_uuid_map.get(gpu_uuid)

                    if gpu_id is not None:
                        # nvidia-smi already gives us ray::function_name, use it directly
                        # If psutil is available, try to get more details
                        if HAS_PSUTIL:
                            try:
                                proc = psutil.Process(pid)
                                cmdline = ' '.join(proc.cmdline())
                                # If process_name is just "python", try to extract from cmdline
                                if process_name in ['python', 'python3', 'python2']:
                                    extracted = self.extract_process_name(cmdline)
                                    if extracted and extracted != cmdline[:30]:
                                        process_name = extracted
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass

                        # Store per GPU (if multiple processes, combine with semicolon)
                        if gpu_id in gpu_processes:
                            gpu_processes[gpu_id] += f"; {process_name}"
                        else:
                            gpu_processes[gpu_id] = process_name

            return gpu_processes

        except Exception as e:
            # Return empty dict on error, don't crash
            return {}

    def extract_process_name(self, cmdline):
        """Extract a meaningful process name from command line."""
        # Look for ray::function_name pattern
        ray_match = re.search(r'ray::([a-zA-Z0-9_.\-:]+)', cmdline)
        if ray_match:
            return ray_match.group(1)

        # Look for Python script name
        py_match = re.search(r'(\w+\.py)', cmdline)
        if py_match:
            return py_match.group(1)

        # Look for main executable at start
        parts = cmdline.split()
        if parts:
            exe = parts[0].split('/')[-1]  # Get basename
            if exe not in ['python', 'python3', 'python2']:
                return exe

            # If it's python, try to get the script name
            for i, part in enumerate(parts):
                if part.endswith('.py'):
                    return part.split('/')[-1]
                elif i > 0 and not part.startswith('-'):
                    # First non-flag argument after python
                    return part.split('/')[-1]

        return cmdline[:30]  # Fallback: first 30 chars

    def parse_nvidia_output(self, output, gpu_processes):
        """Parse nvidia-smi output into structured rows."""
        rows = []
        for line in output.split('\n'):
            if not line.strip():
                continue

            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 7:
                gpu_id = int(parts[1])
                rows.append({
                    'timestamp': parts[0],
                    'gpu_id': parts[1],
                    'utilization_gpu': parts[2],
                    'memory_used': parts[3],
                    'memory_total': parts[4],
                    'temperature': parts[5],
                    'power_draw': parts[6],
                    'process_info': gpu_processes.get(gpu_id, '')
                })

        return rows

    def start_logging(self, stop_event):
        """Main logging loop."""
        # Create output directory if needed
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        # Check if file exists to determine if we need to write headers
        file_exists = self.output_file.exists()

        with open(self.output_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.csv_headers)

            # Write headers if new file
            if not file_exists:
                writer.writeheader()
                f.flush()

            while not stop_event.is_set():
                try:
                    # Query GPU metrics
                    output = self.query_nvidia_smi()

                    # Get process information
                    gpu_processes = self.get_gpu_processes()

                    # Parse with process info
                    rows = self.parse_nvidia_output(output, gpu_processes)

                    # Write to CSV
                    for row in rows:
                        writer.writerow(row)
                    f.flush()

                    # Wait for next interval
                    time.sleep(self.interval)

                except Exception as e:
                    print(f"Error during logging: {e}")
                    time.sleep(self.interval)
