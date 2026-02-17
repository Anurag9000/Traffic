
import csv
import os
import time
from core.gpu import xp as np, to_numpy
from typing import List, Tuple

class VectorStatsRecorder:
    """
    Standardized Metrics Recorder for Vector Engine.
    Scales to 20k+ vehicles.
    
    Features:
    - Real-time metrics logging
    - Trip completion tracking
    - Live export (real-time CSV streaming)
    """
    def __init__(self, engine, output_dir: str = "run_data", prefix: str = "", live_export: bool = False):
        self.engine = engine
        self.output_dir = output_dir
        self.live_export = live_export
        
        m_name = f"{prefix}_metrics.csv" if prefix else "metrics_summary.csv"
        t_name = f"{prefix}_trips.csv" if prefix else "completed_trips.csv"
        
        self.metrics_file = os.path.join(output_dir, m_name)
        self.trips_file = os.path.join(output_dir, t_name)
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Initialize Files
        with open(self.metrics_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["time", "active_vehicles", "throughput_vps", "avg_speed_mps"])
            
        with open(self.trips_file, 'w', newline='') as f:
             writer = csv.writer(f)
             writer.writerow(["vehicle_id", "start_time", "end_time", "duration", "status"])

        self.start_time = time.time()
        self.completed_count_prev = 0
        
        # Live export: keep files open for real-time streaming
        if self.live_export:
            self.metrics_file_handle = open(self.metrics_file, 'a', newline='', buffering=1)  # Line buffered
            self.trips_file_handle = open(self.trips_file, 'a', newline='', buffering=1)
            self.metrics_writer = csv.writer(self.metrics_file_handle)
            self.trips_writer = csv.writer(self.trips_file_handle)
        else:
            self.metrics_file_handle = None
            self.trips_file_handle = None
            self.metrics_writer = None
            self.trips_writer = None

    def log_step(self, current_sim_time: float):
        # 1. Active Metrics
        snapshot = self.engine.get_snapshot()
        if len(snapshot) > 0:
            avg_speed = np.mean(snapshot[:, 3]) # IDX_VEL
        else:
            avg_speed = 0.0
            
        active_count = self.engine.active_count
        
        # 2. Throughput (Trips completed since last check)
        total_completed = len(self.engine.completed_trips)
        new_completions = total_completed - self.completed_count_prev
        
        # 3. Write Metrics (live or buffered)
        row = [
            f"{current_sim_time:.2f}",
            active_count,
            new_completions,
            f"{avg_speed:.2f}"
        ]
        
        if self.live_export and self.metrics_writer:
            # Live export: write immediately with line buffering
            self.metrics_writer.writerow(row)
        else:
            # Buffered export: append to file
            with open(self.metrics_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)
            
        # 4. Write Trips (live or buffered)
        if new_completions > 0:
             new_trips = self.engine.completed_trips[self.completed_count_prev:]
             
             if self.live_export and self.trips_writer:
                 # Live export: write immediately
                 for t in new_trips:
                     vid, start, end, status = t
                     duration = end - start
                     self.trips_writer.writerow([vid, f"{start:.2f}", f"{end:.2f}", f"{duration:.2f}", status])
             else:
                 # Buffered export
                 with open(self.trips_file, 'a', newline='') as f:
                     writer = csv.writer(f)
                     for t in new_trips:
                         vid, start, end, status = t
                         duration = end - start
                         writer.writerow([vid, f"{start:.2f}", f"{end:.2f}", f"{duration:.2f}", status])
        
        self.completed_count_prev = total_completed

    def compute_summary(self):
        """Returns aggregate stats dictionary."""
        trips = self.engine.completed_trips
        if not trips:
            return {
                "total_vehicles": 0,
                "throughput": 0.0,
                "avg_delay": 0.0
            }
            
        durations = [t[2] - t[1] for t in trips]
        
        return {
            "total_vehicles": len(trips),
            "throughput": len(trips) / self.engine.current_time,
            "avg_delay": sum(durations) / len(durations)
        }
    
    def close(self):
        """Close live export file handles if open."""
        if self.live_export:
            if self.metrics_file_handle:
                self.metrics_file_handle.close()
            if self.trips_file_handle:
                self.trips_file_handle.close()
