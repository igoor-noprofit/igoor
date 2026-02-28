FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies for audio and Qt webview
RUN apt-get update && apt-get install -y \
    libxcb-cursor0 \
    libxcb-xinerama0 \
    libxcb-xkbcommon0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-sync1 \
    libxcb-xfixes0 \
    libxcb-xrender0 \
    libxkbcommon-x11-0 \
    portaudio19-dev \
    python3-dev \
    gcc \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Wayland support (alternative to X11)
RUN apt-get update && apt-get install -y \
    libwayland-client0 \
    libwayland-cursor0 \
    libwayland-egl1 \
    libwayland-server0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose FastAPI server port
EXPOSE 9714

# Create a non-root user for running the app
RUN useradd -m -u 1000 igoor && chown -R igoor /app
USER igoor

# Run IGOOR (add --no-gui flag when implemented)
CMD ["python", "main.py"]
