https://chatgpt.com/c/673c50a9-4158-800a-a6f6-f48352fe85c0

import psutil

# Get the total, available, and used memory
memory_info = psutil.virtual_memory()

# Available RAM in bytes
available_ram = memory_info.available

# Convert bytes to megabytes for readability
available_ram_mb = available_ram / (1024 ** 2)

print(f"Available RAM: {available_ram_mb:.2f} MB")

# Set a memory threshold in bytes (e.g., 100 MB)
memory_threshold = 100 * 1024 * 1024

if memory_info.available < memory_threshold:
    print("Warning: Low available memory!")

# CPU

import psutil

# Get the overall CPU usage percentage (across all cores)
cpu_usage = psutil.cpu_percent(interval=1)  # 1-second interval for averaging

print(f"Overall CPU Usage: {cpu_usage}%")