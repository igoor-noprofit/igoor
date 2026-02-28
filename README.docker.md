# IGOOR - Docker Setup

## Quick Start

### Build the image
```bash
docker build -t igoor:latest .
```

### Run the container
```bash
# Basic (headless, access via web browser)
docker run -p 9714:9714 igoor:latest

# With persistent data volume
docker run -d \
  -p 9714:9714 \
  -v igoor-data:/home/igoor/.igoor \
  igoor:latest
```

### Access IGOOR
Open your browser and navigate to:
```
http://localhost:9714
```

## Docker Compose (Recommended)

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  igoor:
    build: .
    container_name: igoor
    ports:
      - "9714:9714"
    volumes:
      - igoor-data:/home/igoor/.igoor
    restart: unless-stopped
    environment:
      - PYTHONUNBUFFERED=1
    # Add these if you need camera/audio access:
    # devices:
    #   - /dev/video0:/dev/video0  # Camera for eye-tracking
    #   - /dev/snd:/dev/snd  # Audio for TTS/ASR

volumes:
  igoor-data:
```

Run with:
```bash
docker-compose up -d
```

## Features

✅ **Working:**
- Full backend with all plugins
- FastAPI server on port 9714
- SQLite database persistence
- Plugin system (conversation, memory, shortcuts, etc.)
- Web-based interface

⚠️ **Limitations (Headless mode):**
- No native GUI window (access via browser only)
- Camera access requires device mapping
- Audio access requires device mapping
- Eye-tracking needs camera configuration

## Troubleshooting

### Check logs
```bash
docker logs igoor
```

### Stop container
```bash
docker stop igoor
docker rm igoor
```

### Persistent data
Database and settings are stored in the `igoor-data` volume. To backup:
```bash
docker run --rm -v igoor-data:/data -v $(pwd):/backup alpine tar czf /backup/igoor-backup.tar.gz /data
```

## Development

### Run with hot-reload
```bash
docker-compose up --build
```

### Access container shell
```bash
docker exec -it igoor bash
```

## Current Status

- ✅ Backend fully operational
- ✅ All plugins load correctly
- ✅ Cross-platform compatibility fixed
- ⚠️ GUI requires X11/Wayland forwarding (advanced)
- 🌐 Web interface recommended for Docker usage
