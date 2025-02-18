from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
import psutil, os, time, threading,asyncio
from dotenv import load_dotenv
load_dotenv()
from context_manager import context_manager

# Get the current process
process = psutil.Process(os.getpid())

class Ramcpu(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name,pm)
        
    @hookimpl
    def startup(self):
        self.settings = self.get_my_settings()
        print(f"Loaded settings for ramcpu: {self.settings}")  # Debug print
        self.timeout = int(self.settings.get("timeout", 1))
        self.battery_threshold = int(self.settings.get("battery_threshold", 20))
        self.warning_timeout = int(self.settings.get("warning_timeout", 300))
        self.last_battery_warning = 0
        # Send initial settings to frontend
        initial_settings = {
            "type": "settings",
            "settings": {
                "timeout": self.timeout,
                "battery_threshold": self.battery_threshold,
                "warning_timeout": self.warning_timeout
            }
        }
        self.send_message_to_frontend(initial_settings)

    @hookimpl
    def gui_ready(self):
        monitor_thread = threading.Thread(target=self.monitor_usage, daemon=True)
        monitor_thread.start()
    # Function to print CPU and RAM usage
    def monitor_usage(self):
        while True:
            # Process-specific CPU usage
            cpu_usage = process.cpu_percent(interval=1)  # 1 second interval for accurate CPU measurement
            # Total system CPU usage
            total_cpu_usage = psutil.cpu_percent(interval=1)
            
            # Memory information
            memory_usage = process.memory_info().rss / (1024 * 1024)  # Convert bytes to MB
            system_memory = psutil.virtual_memory()
            total_memory_used = system_memory.used / (1024 * 1024)  # Convert to MB
            total_memory = system_memory.total / (1024 * 1024)  # Convert to MB
            memory_percent = system_memory.percent
            
            usage_data = {
                "cpu_usage": cpu_usage,          # Process CPU usage
                "total_cpu_usage": total_cpu_usage,  # System-wide CPU usage
                "memory_usage": memory_usage,
                "total_memory_used": total_memory_used,
                "total_memory": total_memory,
                "memory_percent": memory_percent
            }
            
            # Add battery monitoring
            battery = psutil.sensors_battery()
            battery_data = {
                "percentage": 0,
                "power_plugged": True,
                "battery_threshold": self.battery_threshold  # Pass the threshold to frontend
            }
            
            if battery:
                battery_data["percentage"] = battery.percent
                battery_data["power_plugged"] = battery.power_plugged
                
                # Check if battery is below threshold and not plugged in
                current_time = time.time()
                if (battery.percent <= self.battery_threshold and 
                    not battery.power_plugged and 
                    current_time - self.last_battery_warning > self.warning_timeout):
                    print ("************* WARNING THE USER")
                    self.last_battery_warning = current_time
                    # asyncio.create_task(self.pm.trigger_hook(hook_name="speak", message=msg))
                    # asyncio.run(self.pm.trigger_hook(hook_name="speak", message="OK tests"))
                else:
                    elapsed_time = current_time - self.last_battery_warning
                    print(f"Time since last battery warning: {elapsed_time:.1f} seconds")
            
            usage_data.update(battery_data)
            self.send_message_to_frontend(usage_data)
            time.sleep(self.timeout)
    
    # Function to print CPU and RAM usage
    def print_usage(self):
        # Get the CPU percentage
        cpu_usage = process.cpu_percent(interval=1)
        
        # Get memory usage in MB
        memory_usage = process.memory_info().rss / (1024 * 1024)
        
        print(f"CPU Usage: {cpu_usage}%")
        print(f"Memory Usage: {memory_usage:.2f} MB")
