# WBDG PDF Scraper - Standalone Docker Edition

**Copyright (c) 2025 DTRIQ LLC. All rights reserved.**  
Licensed under MIT License with Additional Terms - See [LICENSE](LICENSE)

## Overview

A production-ready standalone WBDG (Whole Building Design Guide) PDF scraper that downloads UFC documents with incremental updates and cloud storage support. Originally designed for Palantir Foundry, now refactored for universal Docker deployment.

## ⚠️ Security Notice

**This repository contains NO sensitive credentials.** All tokens and API keys must be provided via environment variables. See [SECURITY.md](SECURITY.md) for complete security guidelines.

## Key Features

- **✅ Incremental Downloads**: Only downloads new or changed documents
- **☁️ Cloud Storage**: AWS S3, Azure Blob, Google Cloud Storage support  
- **🐳 Docker Ready**: Containerized for any environment
- **📊 Monitoring**: Comprehensive logging and progress tracking
- **🔒 Secure**: No hardcoded credentials, environment-based configuration
- **⚡ Scalable**: Handles ~700 large files efficiently

## Quick Start

### 1. Setup Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your credentials (NEVER commit .env file)
nano .env
```

### 2. Run with Docker

```bash
# Build image
docker build -t wbdg-scraper .

# Run with local storage
docker run --rm --env-file .env -v $(pwd)/output:/app/output wbdg-scraper

# Or use the provided script
./run_docker.sh
```

### 3. Check Status

```bash
# View incremental download status
python -m myproject.datasets.wbdg_scraper --status --output-dir ./output
```

## Configuration

### Local Development
```bash
pip install -r requirements.txt
PYTHONPATH=src python -m myproject.datasets.wbdg_scraper --output-dir ./output
```

### Cloud Storage Examples

**AWS S3:**
```bash
export WBDG_STORAGE_TYPE=s3
export WBDG_STORAGE_BUCKET=wbdg-documents
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
```

**Azure Blob:**
```bash
export WBDG_STORAGE_TYPE=azure
export AZURE_STORAGE_ACCOUNT=youraccount
export AZURE_STORAGE_KEY=your-key
export AZURE_CONTAINER_NAME=wbdg-documents
```

**Google Cloud:**
```bash
export WBDG_STORAGE_TYPE=gcs
export WBDG_STORAGE_BUCKET=wbdg-documents
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

## Documentation

- **[CLAUDE.md](CLAUDE.md)**: Complete usage guide and deployment examples
- **[PROJECT_OUTLINE.md](PROJECT_OUTLINE.md)**: Technical architecture and migration notes
- **[cloud_storage_examples.md](cloud_storage_examples.md)**: Detailed cloud deployment configurations
- **[SECURITY.md](SECURITY.md)**: Security guidelines and best practices

## Testing

```bash
# Unit tests
PYTHONPATH=src python -m pytest src/test/ -v

# Functionality verification  
python simple_test.py

# Incremental download testing
python test_incremental.py

# Large-scale simulation (700+ files)
PYTHONPATH=src python test_large_files.py --file-count 100
```

## Command Line Usage

```bash
# Show help
python -m myproject.datasets.wbdg_scraper --help

# Full scrape with incremental updates
python -m myproject.datasets.wbdg_scraper --output-dir /data

# Crawl only (discovery mode)
python -m myproject.datasets.wbdg_scraper --crawl-only --output-dir /data

# Check incremental status
python -m myproject.datasets.wbdg_scraper --status --output-dir /data
```

## Project Structure

```
transforms-python/
├── src/myproject/datasets/
│   └── wbdg_scraper.py          # Main scraper with incremental downloads
├── src/test/                    # Comprehensive test suite
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Container configuration
├── .env.example                 # Environment template (copy to .env)
├── LICENSE                      # MIT License with DTRIQ terms
├── SECURITY.md                  # Security guidelines
└── Documentation files
```

## Performance

- **Download Rate**: ~2.7 files/second
- **Memory Usage**: <100MB with chunked downloads
- **File Support**: Up to 100MB per PDF
- **Concurrency**: Configurable (tested with 5 workers)
- **Change Detection**: SHA-256 checksums and metadata tracking

## License & Copyright

Copyright (c) 2025 DTRIQ LLC. All rights reserved.

Licensed under MIT License with Additional Terms:
- Attribution required for derivative works
- Commercial scraping services require written permission
- See [LICENSE](LICENSE) for complete terms

## Support

For questions or commercial licensing inquiries, contact DTRIQ LLC.

**⚠️ Security Issues**: Report to security contact (see SECURITY.md), not public issues.