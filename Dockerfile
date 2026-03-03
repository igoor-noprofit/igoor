FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV IGOOR_CLI=True

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    portaudio19-dev \
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
