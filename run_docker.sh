#!/bin/bash
# Docker deployment script for WBDG scraper

set -e

echo "=== WBDG Docker Deployment Script ==="

# Build the Docker image
echo "Building Docker image..."
docker build -t wbdg-scraper .

# Create output directory
mkdir -p docker_output

# Run the scraper in Docker
echo "Running WBDG scraper in Docker..."
docker run --rm \
    -v "$(pwd)/docker_output:/app/output" \
    -e WBDG_LOG_LEVEL=INFO \
    wbdg-scraper

echo "Scraping complete! Check docker_output/ for results."
echo "Logs: docker_output/logs/"
echo "PDFs: docker_output/pdfs/"