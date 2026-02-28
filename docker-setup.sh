#!/bin/bash
# IGOOR Docker Setup Script

set -e

echo "🐳 IGOOR Docker Setup"
echo "======================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed."
    echo "   Install Docker from: https://docs.docker.com/get-docker/"
    exit 1
fi

echo "✅ Docker found: $(docker --version)"
echo ""

# Build the image
echo "📦 Building IGOOR Docker image..."
docker build -t igoor:latest .

echo ""
echo "✅ Build complete!"
echo ""
echo "🚀 Starting IGOOR container..."
echo ""

# Run the container
docker run -d \
  --name igoor \
  -p 9714:9714 \
  -v igoor-data:/home/igoor/.igoor \
  --restart unless-stopped \
  igoor:latest

echo ""
echo "✅ IGOOR is running!"
echo ""
echo "📱 Access IGOOR at: http://localhost:9714"
echo ""
echo "📋 View logs with: docker logs -f igoor"
echo "🛑 Stop with: docker stop igoor"
echo ""
