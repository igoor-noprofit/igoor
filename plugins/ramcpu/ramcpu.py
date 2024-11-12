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
        monitor_thread = threading.Thread(target=self.monitor_usage, daemon=True)
        monitor_thread.start()
        
    # Function to print CPU and RAM usage
    def monitor_usage(self):
        while True:
            cpu_usage = process.cpu_percent(interval=1)  # 1 second interval for accurate CPU measurement
            memory_usage = process.memory_info().rss / (1024 * 1024)  # Convert bytes to MB
            
            usage_data = {
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage
            }
            
            self.send_message_to_frontend(usage_data)
            time.sleep(2)  # Print every 5 seconds
    
    # Function to print CPU and RAM usage
    def print_usage():
        # Get the CPU percentage
        cpu_usage = process.cpu_percent(interval=1)
        
        # Get memory usage in MB
        memory_usage = process.memory_info().rss / (1024 * 1024)
        
        print(f"CPU Usage: {cpu_usage}%")
        print(f"Memory Usage: {memory_usage:.2f} MB")
        
