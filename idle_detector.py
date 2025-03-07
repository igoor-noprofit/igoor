# idle_detector.py
'''
Key features of this module:

Object-oriented design: Use the IdleDetector class for continuous monitoring
Simple one-off function: Use get_idle_time() for one-time checks
Callback support: Register a function to be called when idle state changes
Customizable thresholds: Set your own idle timeout and check frequency
Threading: Monitoring runs in background without blocking your main application
Platform detection: Automatically uses the right method for each OS
Error handling: Gracefully handles failures in platform-specific implementations
'''

import time
import platform
import threading

class IdleDetector:
    def __init__(self, callback=None, idle_threshold=60, check_interval=5):
        """
        Initialize the idle detector.
        
        Args:
            callback (callable, optional): Function to call when idle state changes. 
            It receives a single boolean parameter indicating if user is idle.
            idle_threshold (int, optional): Time in seconds before user is considered idle. Defaults to 60.
            check_interval (int, optional): Interval in seconds between idle checks. Defaults to 5.
        """
        self.callback = callback
        self.idle_threshold = idle_threshold
        self.check_interval = check_interval
        self._running = False
        self._thread = None
        self._current_idle_state = False
        
    def start(self):
        """Start monitoring for user inactivity."""
        if self._running:
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._monitor_idle, daemon=True)
        self._thread.start()
        return self
        
    def stop(self):
        """Stop monitoring for user inactivity."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self.check_interval + 1)
        self._thread = None
        return self
        
    def is_idle(self):
        """
        Check if the user is currently idle.
        
        Returns:
            bool: True if user is idle for longer than the threshold, False otherwise.
        """
        return self.get_idle_time() >= self.idle_threshold
        
    def get_idle_time(self):
        """
        Get the current idle time in seconds.
        
        Returns:
            float: The idle time in seconds.
        """
        system = platform.system()
        
        if system == 'Windows':
            return self._get_idle_time_windows()
        elif system == 'Darwin':  # macOS
            return self._get_idle_time_macos()
        elif system == 'Linux':
            return self._get_idle_time_linux()
        else:
            raise NotImplementedError(f"Idle time detection not implemented for {system}")
    
    def _monitor_idle(self):
        """Internal method to continuously monitor idle state."""
        while self._running:
            is_idle = self.is_idle()
            
            # If idle state changed and a callback is set, call it
            if is_idle != self._current_idle_state and self.callback:
                self._current_idle_state = is_idle
                try:
                    self.callback(is_idle)
                except Exception as e:
                    print(f"Error in idle callback: {e}")
            
            time.sleep(self.check_interval)
    
    def _get_idle_time_windows(self):
        """Get idle time on Windows platforms."""
        try:
            import ctypes
            
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [
                    ('cbSize', ctypes.c_uint),
                    ('dwTime', ctypes.c_uint),
                ]
            
            lastInputInfo = LASTINPUTINFO()
            lastInputInfo.cbSize = ctypes.sizeof(lastInputInfo)
            
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lastInputInfo)):
                millis = ctypes.windll.kernel32.GetTickCount() - lastInputInfo.dwTime
                return millis / 1000.0  # Convert to seconds
        except Exception as e:
            print(f"Error getting Windows idle time: {e}")
        return 0
    
    def _get_idle_time_macos(self):
        """Get idle time on macOS platforms."""
        try:
            import subprocess
            output = subprocess.check_output(['ioreg', '-c', 'IOHIDSystem']).decode('utf-8')
            for line in output.split('\n'):
                if 'HIDIdleTime' in line:
                    # Extract the hexadecimal value
                    hex_value = line.split('=')[-1].strip().replace('\"', '')
                    # Convert to seconds (HIDIdleTime is in nanoseconds)
                    return int(hex_value, 16) / 1000000000
        except Exception as e:
            print(f"Error getting macOS idle time: {e}")
        return 0
    
    def _get_idle_time_linux(self):
        """Get idle time on Linux platforms."""
        # First try xprintidle
        try:
            import subprocess
            idle_time = subprocess.check_output(['xprintidle']).decode('utf-8').strip()
            return int(idle_time) / 1000.0  # Convert to seconds
        except Exception:
            # Try X11 method
            try:
                from Xlib import display
                from Xlib.ext import screensaver
                
                d = display.Display()
                info = screensaver.query_info(d, d.screen().root)
                return info.idle / 1000.0  # Convert to seconds
            except Exception as e:
                print(f"Error getting Linux idle time: {e}")
        return 0

# For convenience, provide a simple function to get current idle time
def get_idle_time():
    """
    Get the current system idle time in seconds.
    
    Returns:
        float: The idle time in seconds.
    """
    detector = IdleDetector()
    return detector.get_idle_time()