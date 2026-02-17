"""
Traffic Data Module - Time-Varying Profiles, Live Data, and Historical Replay

Provides:
1. TrafficProfile: Predefined time-varying traffic demand patterns
2. LiveTrafficData: TomTom API integration for real-time traffic
3. HistoricalReplay: Replay traffic from CSV files
"""

from typing import Dict, List, Tuple, Optional
import csv
import os


class TrafficProfile:
    """
    Time-varying traffic demand profiles.
    
    Provides predefined patterns for different scenarios:
    - morning_rush: Peak traffic 7-9 AM
    - evening_rush: Peak traffic 5-7 PM
    - weekend: Lower overall traffic
    - event: Sudden spike in traffic
    """
    
    PROFILES = {
        'morning_rush': [
            (0, 0.2),      # 00:00 - low (night)
            (3600, 0.2),   # 01:00 - low
            (7200, 0.2),   # 02:00 - low
            (10800, 0.2),  # 03:00 - low
            (14400, 0.3),  # 04:00 - starting to increase
            (18000, 0.4),  # 05:00 - increasing
            (21600, 0.6),  # 06:00 - building up
            (25200, 1.2),  # 07:00 - rush hour starts
            (28800, 1.8),  # 08:00 - peak
            (32400, 1.5),  # 09:00 - declining
            (36000, 0.8),  # 10:00 - mid-morning
            (39600, 0.6),  # 11:00 - normal
            (43200, 0.5),  # 12:00 - lunch
            (46800, 0.6),  # 13:00 - afternoon
            (50400, 0.7),  # 14:00 - afternoon
            (54000, 0.8),  # 15:00 - building
            (57600, 1.0),  # 16:00 - building
            (61200, 1.4),  # 17:00 - evening rush
            (64800, 1.6),  # 18:00 - peak
            (68400, 1.2),  # 19:00 - declining
            (72000, 0.6),  # 20:00 - evening
            (75600, 0.4),  # 21:00 - night
            (79200, 0.3),  # 22:00 - night
            (82800, 0.2),  # 23:00 - night
        ],
        'evening_rush': [
            (0, 0.3),      # 00:00 - low
            (14400, 0.4),  # 04:00 - low
            (28800, 0.6),  # 08:00 - morning
            (43200, 0.5),  # 12:00 - midday
            (57600, 1.0),  # 16:00 - building
            (61200, 1.6),  # 17:00 - peak
            (64800, 1.8),  # 18:00 - peak
            (68400, 1.4),  # 19:00 - declining
            (72000, 0.7),  # 20:00 - evening
            (79200, 0.3),  # 22:00 - night
        ],
        'weekend': [
            (0, 0.1),      # 00:00 - very low
            (28800, 0.3),  # 08:00 - slow start
            (36000, 0.5),  # 10:00 - picking up
            (43200, 0.7),  # 12:00 - lunch rush
            (50400, 0.6),  # 14:00 - afternoon
            (64800, 0.5),  # 18:00 - evening
            (79200, 0.2),  # 22:00 - night
        ],
        'event': [
            (0, 0.5),      # 00:00 - normal
            (3600, 0.5),   # 01:00 - normal
            (7200, 2.5),   # 02:00 - EVENT STARTS (sudden spike)
            (10800, 3.0),  # 03:00 - peak
            (14400, 2.0),  # 04:00 - declining
            (18000, 0.8),  # 05:00 - back to normal
            (21600, 0.5),  # 06:00 - normal
        ],
    }
    
    @staticmethod
    def get_rate(profile_name: str, current_time: float, base_rate: float = 1.0) -> float:
        """
        Get spawn rate for given time in the profile.
        
        Args:
            profile_name: Name of the profile ('morning_rush', 'evening_rush', etc.)
            current_time: Current simulation time (seconds)
            base_rate: Base spawn rate to multiply by profile factor
        
        Returns:
            Spawn rate (vehicles/lane/second)
        """
        if profile_name not in TrafficProfile.PROFILES:
            return base_rate
        
        profile = TrafficProfile.PROFILES[profile_name]
        
        # Handle time wrapping (24-hour cycle)
        time_in_day = current_time % 86400  # 86400 seconds in a day
        
        # Find surrounding time points
        if time_in_day <= profile[0][0]:
            return base_rate * profile[0][1]
        if time_in_day >= profile[-1][0]:
            return base_rate * profile[-1][1]
        
        # Linear interpolation
        for i in range(len(profile) - 1):
            t1, factor1 = profile[i]
            t2, factor2 = profile[i + 1]
            if t1 <= time_in_day <= t2:
                alpha = (time_in_day - t1) / (t2 - t1)
                factor = factor1 + alpha * (factor2 - factor1)
                return base_rate * factor
        
        return base_rate


class LiveTrafficData:
    """
    TomTom API integration for live traffic data.
    
    Note: Requires TomTom API key and active internet connection.
    """
    
    def __init__(self, api_key: str, bbox: Tuple[float, float, float, float]):
        """
        Initialize live traffic data fetcher.
        
        Args:
            api_key: TomTom API key
            bbox: Bounding box (min_lon, min_lat, max_lon, max_lat)
        """
        self.api_key = api_key
        self.bbox = bbox
        self.last_fetch_time = 0.0
        self.fetch_interval = 300.0  # Fetch every 5 minutes
        self.cached_flow_data = {}
    
    def fetch_current_flow(self) -> Dict:
        """
        Fetch current traffic flow from TomTom API.
        
        Returns:
            Dictionary mapping road segments to flow data
        """
        try:
            import requests
            
            min_lon, min_lat, max_lon, max_lat = self.bbox
            
            # TomTom Traffic Flow API endpoint
            url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
            params = {
                'key': self.api_key,
                'point': f"{(min_lat + max_lat) / 2},{(min_lon + max_lon) / 2}",
                'unit': 'KMPH'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            self.cached_flow_data = data
            return data
        
        except Exception as e:
            print(f"Warning: Failed to fetch live traffic data: {e}")
            return self.cached_flow_data
    
    def map_to_spawn_rates(self, flow_data: Dict, base_rate: float = 1.0) -> Dict[int, float]:
        """
        Convert flow data to spawn rates per lane.
        
        Args:
            flow_data: Raw flow data from TomTom API
            base_rate: Base spawn rate
        
        Returns:
            Dictionary mapping lane_id -> spawn_rate
        """
        lane_rates = {}
        
        # Extract flow information
        if 'flowSegmentData' in flow_data:
            segment = flow_data['flowSegmentData']
            current_speed = segment.get('currentSpeed', 50)
            free_flow_speed = segment.get('freeFlowSpeed', 50)
            
            # Calculate congestion factor (0.0 = free flow, 1.0 = stopped)
            if free_flow_speed > 0:
                congestion = 1.0 - (current_speed / free_flow_speed)
            else:
                congestion = 0.0
            
            # Higher congestion = more vehicles = higher spawn rate
            # This is a simplified model
            rate_multiplier = 1.0 + (congestion * 2.0)
            
            # Apply to all lanes (in real implementation, map to specific lanes)
            for lane_id in range(100):  # Placeholder
                lane_rates[lane_id] = base_rate * rate_multiplier
        
        return lane_rates
    
    def update(self, current_time: float) -> Dict[int, float]:
        """
        Update traffic data if needed.
        
        Args:
            current_time: Current simulation time
        
        Returns:
            Updated spawn rates per lane
        """
        if current_time - self.last_fetch_time >= self.fetch_interval:
            flow_data = self.fetch_current_flow()
            self.last_fetch_time = current_time
            return self.map_to_spawn_rates(flow_data)
        
        return self.map_to_spawn_rates(self.cached_flow_data)


class HistoricalReplay:
    """
    Replay traffic from CSV file.
    
    CSV Format:
        time,lane_id,vehicle_type,target_x,target_y
        0.0,5,0,100,200
        0.1,12,1,150,250
        ...
    """
    
    def __init__(self, csv_path: str):
        """
        Initialize historical replay.
        
        Args:
            csv_path: Path to CSV file with historical traffic data
        """
        self.csv_path = csv_path
        self.data = self._load_csv(csv_path)
        self.current_index = 0
    
    def _load_csv(self, csv_path: str) -> List[Dict]:
        """Load and parse CSV file."""
        if not os.path.exists(csv_path):
            print(f"Warning: CSV file not found: {csv_path}")
            return []
        
        data = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append({
                    'time': float(row['time']),
                    'lane_id': int(row['lane_id']),
                    'vehicle_type': int(row.get('vehicle_type', 0)),
                    'target_x': float(row.get('target_x', 0)),
                    'target_y': float(row.get('target_y', 0)),
                })
        
        # Sort by time
        data.sort(key=lambda x: x['time'])
        return data
    
    def get_spawn_schedule(self, time: float, dt: float = 0.1) -> List[Dict]:
        """
        Get vehicles to spawn at given time.
        
        Args:
            time: Current simulation time
            dt: Time window for spawning
        
        Returns:
            List of spawn events: [{'lane_id': int, 'vehicle_type': int, 'target': (x, y)}, ...]
        """
        spawns = []
        
        # Find all events in time window [time, time + dt]
        while self.current_index < len(self.data):
            event = self.data[self.current_index]
            
            if event['time'] > time + dt:
                break
            
            if event['time'] >= time:
                spawns.append({
                    'lane_id': event['lane_id'],
                    'vehicle_type': event['vehicle_type'],
                    'target': (event['target_x'], event['target_y'])
                })
            
            self.current_index += 1
        
        return spawns
    
    def reset(self):
        """Reset replay to beginning."""
        self.current_index = 0
