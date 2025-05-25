# WBDG PDF Scraper - Claude Code Project Documentation

## Project Overview
This project provides a standalone WBDG (Whole Building Design Guide) PDF scraper that has been reconfigured from a Foundry-specific transform to run independently in Docker environments. The scraper downloads UFC (Unified Facilities Criteria) PDFs and can be configured for cloud storage backends.

## Architecture

### Core Components
- **WBDGScraper Class**: Main scraper implementation with crawling, downloading, and validation
- **Standalone CLI**: Command-line interface for direct execution
- **Docker Support**: Containerized deployment with configurable outputs
- **Testing Suite**: Comprehensive unit tests and large-scale testing tools
- **Cloud Storage**: Configurable backends for S3, Azure Blob, GCS

## Key Features

### 🔄 **Incremental Updates**
- **Change Detection**: Downloads only new or modified documents
- **Checksum Validation**: SHA-256 checksums prevent duplicate downloads
- **Metadata Tracking**: Maintains download history and file states
- **Resume Capability**: Can restart interrupted scraping sessions

### 🌐 **Cloud Storage Support**
- **AWS S3**: Native boto3 integration
- **Azure Blob Storage**: Azure SDK support
- **Google Cloud Storage**: GCS client library
- **Local Filesystem**: Default fallback option

### 🛡️ **Error Handling & Resilience**
- **Retry Logic**: Exponential backoff for failed requests
- **Rate Limiting**: Configurable delays between requests
- **File Validation**: PDF format verification before storage
- **Size Limits**: Configurable maximum file sizes
- **Timeout Handling**: Network request timeouts

### 📊 **Monitoring & Logging**
- **Structured Logging**: JSON logs for parsing and analysis
- **Progress Tracking**: Real-time progress bars
- **Performance Metrics**: Download speeds, success rates, error counts
- **Crawl Logs**: Detailed logs of all scraping activities

## Configuration

### Environment Variables
```bash
# Basic Configuration
WBDG_BASE_URL=https://www.wbdg.org/
WBDG_OUTPUT_DIR=/app/output
WBDG_LOG_LEVEL=INFO

# Cloud Storage Configuration
WBDG_STORAGE_TYPE=s3|azure|gcs|local
WBDG_STORAGE_BUCKET=your-bucket-name
WBDG_STORAGE_PREFIX=wbdg-pdfs/

# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1

# Azure Blob Configuration
AZURE_STORAGE_ACCOUNT=your-account
AZURE_STORAGE_KEY=your-key
AZURE_CONTAINER_NAME=your-container

# Google Cloud Storage Configuration
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GCS_PROJECT_ID=your-project-id

# Performance Tuning
WBDG_REQUEST_DELAY=0.25
WBDG_MAX_RETRIES=3
WBDG_CHUNK_SIZE=8192
WBDG_MAX_FILE_SIZE=104857600
WBDG_CONCURRENT_DOWNLOADS=5
```

## Usage Examples

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run with local storage
PYTHONPATH=src python -m myproject.datasets.wbdg_scraper \
    --output-dir ./output \
    --log-level INFO

# Crawl only (no downloads)
PYTHONPATH=src python -m myproject.datasets.wbdg_scraper \
    --crawl-only \
    --output-dir ./crawl_results
```

### Docker Deployment
```bash
# Build image
docker build -t wbdg-scraper .

# Run with local storage
docker run --rm \
    -v $(pwd)/output:/app/output \
    -e WBDG_LOG_LEVEL=INFO \
    wbdg-scraper

# Run with S3 storage
docker run --rm \
    -e WBDG_STORAGE_TYPE=s3 \
    -e WBDG_STORAGE_BUCKET=my-pdfs-bucket \
    -e AWS_ACCESS_KEY_ID=AKIA... \
    -e AWS_SECRET_ACCESS_KEY=... \
    wbdg-scraper

# Use provided script
./run_docker.sh
```

### Cloud Deployment Examples

#### AWS ECS/Fargate
```yaml
# ecs-task-definition.json
{
  "family": "wbdg-scraper",
  "taskRoleArn": "arn:aws:iam::123456789012:role/WBDGScraperRole",
  "containerDefinitions": [{
    "name": "wbdg-scraper",
    "image": "your-registry/wbdg-scraper:latest",
    "environment": [
      {"name": "WBDG_STORAGE_TYPE", "value": "s3"},
      {"name": "WBDG_STORAGE_BUCKET", "value": "wbdg-documents"},
      {"name": "WBDG_LOG_LEVEL", "value": "INFO"}
    ]
  }]
}
```

#### Kubernetes CronJob
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: wbdg-scraper
spec:
  schedule: "0 6 * * *"  # Daily at 6 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: wbdg-scraper
            image: wbdg-scraper:latest
            env:
            - name: WBDG_STORAGE_TYPE
              value: "gcs"
            - name: WBDG_STORAGE_BUCKET
              value: "wbdg-documents"
            - name: GOOGLE_APPLICATION_CREDENTIALS
              value: "/etc/gcp/service-account.json"
            volumeMounts:
            - name: gcp-key
              mountPath: /etc/gcp
          volumes:
          - name: gcp-key
            secret:
              secretName: gcp-service-account
          restartPolicy: OnFailure
```

## Testing

### Unit Tests
```bash
# Run all tests
PYTHONPATH=src python -m pytest src/test/ -v

# Run specific test categories
PYTHONPATH=src python -m pytest src/test/test_wbdg_scraper.py::TestWBDGScraper::test_crawl_for_pdfs_simple -v

# Run with coverage
PYTHONPATH=src python -m pytest src/test/ --cov=myproject.datasets.wbdg_scraper
```

### Large-Scale Testing
```bash
# Test with mock data (safe)
PYTHONPATH=src python test_large_files.py --file-count 100 --output-dir test_results

# Stress test with concurrent downloads
PYTHONPATH=src python test_large_files.py --file-count 50 --concurrent --max-workers 10

# Test against real WBDG (use cautiously)
PYTHONPATH=src python test_large_files.py --real --file-count 10
```

### Verification Tests
```bash
# Basic functionality verification
python simple_test.py

# Docker build verification
docker build -t wbdg-scraper-test . && echo "Build successful"
```

## Monitoring & Troubleshooting

### Log Analysis
```bash
# View real-time logs
tail -f output/logs/scraper.log

# Parse JSON logs
cat output/logs/crawl_log.json | jq '.[] | select(.event_type == "download_error")'

# Monitor download progress
grep "Downloaded:" output/logs/scraper.log | tail -10
```

### Common Issues

#### High Memory Usage
- Reduce `WBDG_CHUNK_SIZE` for memory-constrained environments
- Lower `WBDG_CONCURRENT_DOWNLOADS` to reduce parallel processing
- Monitor container memory limits in orchestration platforms

#### Rate Limiting
- Increase `WBDG_REQUEST_DELAY` if receiving 429 responses
- Implement exponential backoff in retry logic
- Consider using multiple source IPs for large-scale scraping

#### Storage Errors
- Verify cloud storage credentials and permissions
- Check bucket/container existence and access policies
- Monitor storage quotas and billing limits

## Development Guidelines

### Code Style
- Follow PEP 8 conventions
- Use type hints for all functions
- Document all public methods with docstrings
- Maintain test coverage above 90%

### Adding New Storage Backends
1. Implement storage interface in `storage_backends.py`
2. Add configuration validation
3. Update environment variable documentation
4. Add integration tests
5. Update Docker image with required dependencies

### Performance Optimization
- Profile code with `cProfile` for bottlenecks
- Use `aiohttp` for async HTTP requests in high-throughput scenarios
- Implement connection pooling for cloud storage
- Consider CDN caching for frequently accessed documents

## Security Considerations

### Credentials Management
- Never hardcode credentials in source code
- Use environment variables or secret management systems
- Rotate access keys regularly
- Apply principle of least privilege for storage permissions

### Network Security
- Use HTTPS for all external communications
- Validate SSL certificates
- Implement request signing for cloud APIs
- Monitor for suspicious download patterns

### Data Privacy
- Ensure compliance with data retention policies
- Implement secure deletion for temporary files
- Log access patterns for audit purposes
- Consider encryption at rest for sensitive documents

## Deployment Checklist

### Pre-Deployment
- [ ] Configure storage backend credentials
- [ ] Set appropriate log levels
- [ ] Verify network connectivity to WBDG
- [ ] Test storage write permissions
- [ ] Configure monitoring and alerting

### Post-Deployment
- [ ] Monitor initial crawl completion
- [ ] Verify document download integrity
- [ ] Check storage usage and costs
- [ ] Set up automated backups
- [ ] Configure maintenance schedules

## Support & Maintenance

### Regular Tasks
- Monitor storage costs and usage patterns
- Update dependencies and security patches
- Review and rotate access credentials
- Analyze crawl logs for errors or changes
- Backup configuration and metadata

### Scaling Considerations
- Implement horizontal scaling for large document sets
- Use distributed storage for high availability
- Consider CDN integration for global access
- Implement caching layers for frequently accessed documents

---

For additional support or feature requests, refer to the project repository or contact the development team.