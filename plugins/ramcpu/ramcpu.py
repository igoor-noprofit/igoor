from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
import psutil, os, time, threading
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
        self.timeout = int(self.settings.get("timeout", 1))

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
            
            self.send_message_to_frontend(usage_data)
            time.sleep(self.timeout)
    
    # Function to print CPU and RAM usage
    def print_usage():
        # Get the CPU percentage
        cpu_usage = process.cpu_percent(interval=1)
        
        # Get memory usage in MB
        memory_usage = process.memory_info().rss / (1024 * 1024)
        
        print(f"CPU Usage: {cpu_usage}%")
        print(f"Memory Usage: {memory_usage:.2f} MB")
        
