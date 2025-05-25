# WBDG PDF Scraper - Docker Configuration
# Copyright (c) 2025 DTRIQ LLC. All rights reserved.
# Licensed under MIT License with Additional Terms

# Use Python 3.11 as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Set Python path to include src directory
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Create output directory
RUN mkdir -p /app/output

# Set default environment variables
ENV WBDG_BASE_URL=https://www.wbdg.org/
ENV WBDG_OUTPUT_DIR=/app/output
ENV WBDG_LOG_LEVEL=INFO

# Default command to run the standalone scraper
CMD ["python", "-m", "myproject.datasets.wbdg_scraper", "--output-dir", "/app/output"]