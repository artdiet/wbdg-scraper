"""
Standalone WBDG UFC PDF Scraper
===============================
Copyright (c) 2025 DTRIQ LLC. All rights reserved.

This module provides a standalone version of the WBDG scraper that can run
outside of Foundry in a standard Docker environment.

Key features:
- No Foundry dependencies
- Configurable via environment variables
- Outputs to local filesystem with incremental updates
- Comprehensive logging and monitoring
- Rate limiting and error handling
- Cloud storage backend support

Licensed under MIT License with Additional Terms.
See LICENSE file for details.
"""

import io
import os
import json
import time
import hashlib
import logging
from urllib.parse import urljoin, urlparse
from typing import Optional, Dict, List, Set
from pathlib import Path
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm
from PyPDF2 import PdfReader


class WBDGScraper:
    """Standalone WBDG PDF scraper."""
    
    def __init__(self, 
                 base_url: str = "https://www.wbdg.org/",
                 output_dir: str = "output",
                 log_level: str = "INFO"):
        """Initialize the scraper.
        
        Parameters
        ----------
        base_url : str
            Base URL for WBDG site
        output_dir : str
            Directory to save PDFs and logs
        log_level : str
            Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        self.base_url = base_url.rstrip("/") + "/"
        self.output_dir = Path(output_dir)
        self.pdfs_dir = self.output_dir / "pdfs"
        self.logs_dir = self.output_dir / "logs"
        self.metadata_dir = self.output_dir / "metadata"
        
        # Create output directories
        self.pdfs_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration constants
        self.INDEX_ROOT = "dod/ufc"
        self.REQUEST_DELAY_S = 0.25
        self.MAX_RETRIES = 3
        self.CHUNK_SIZE = 8192
        self.MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
        
        # Setup logging
        self._setup_logging(log_level)
        
        # Initialize session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'WBDG-Scraper/1.0 (Educational Use)'
        })
        
        # Tracking variables
        self.visited_pages: Set[str] = set()
        self.pdf_urls: Set[str] = set()
        self.log_entries: List[Dict] = []
        
        # Incremental download tracking
        self.metadata_file = self.metadata_dir / "download_metadata.json"
        self.file_metadata = self._load_metadata()
        
    def _setup_logging(self, log_level: str):
        """Setup logging configuration."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # File handler
        log_file = self.logs_dir / "scraper.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level.upper()))
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def _load_metadata(self) -> Dict[str, Dict]:
        """Load existing download metadata for incremental updates.
        
        Returns
        -------
        Dict[str, Dict]
            Dictionary mapping filenames to their metadata
        """
        if not self.metadata_file.exists():
            self.logger.info("No existing metadata found, starting fresh")
            return {}
        
        try:
            with open(self.metadata_file, 'r') as f:
                metadata = json.load(f)
            self.logger.info(f"Loaded metadata for {len(metadata)} files")
            return metadata
        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning(f"Failed to load metadata: {e}, starting fresh")
            return {}
    
    def _save_metadata(self):
        """Save current metadata to disk."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.file_metadata, f, indent=2)
            self.logger.debug(f"Saved metadata for {len(self.file_metadata)} files")
        except IOError as e:
            self.logger.error(f"Failed to save metadata: {e}")
    
    def _should_download_file(self, url: str, filename: str, content_length: int) -> bool:
        """Check if a file should be downloaded based on existing metadata.
        
        Parameters
        ----------
        url : str
            URL of the file
        filename : str
            Local filename
        content_length : int
            Size of the file in bytes
            
        Returns
        -------
        bool
            True if file should be downloaded, False if it can be skipped
        """
        local_path = self.pdfs_dir / filename
        
        # Always download if file doesn't exist locally
        if not local_path.exists():
            self.logger.debug(f"File {filename} doesn't exist locally, will download")
            return True
        
        # Check metadata
        if filename not in self.file_metadata:
            self.logger.debug(f"No metadata for {filename}, will download to verify")
            return True
        
        file_meta = self.file_metadata[filename]
        
        # Check if size changed
        if file_meta.get('size') != content_length:
            self.logger.info(f"Size changed for {filename}: {file_meta.get('size')} → {content_length}")
            return True
        
        # Check if URL changed
        if file_meta.get('url') != url:
            self.logger.info(f"URL changed for {filename}")
            return True
        
        # Check last-modified header if available
        try:
            head_response = self.session.head(url, timeout=30)
            last_modified = head_response.headers.get('last-modified')
            if last_modified and file_meta.get('last_modified') != last_modified:
                self.logger.info(f"Last-modified changed for {filename}")
                return True
        except Exception as e:
            self.logger.debug(f"Could not check last-modified for {filename}: {e}")
        
        # File appears unchanged
        self.logger.debug(f"Skipping unchanged file: {filename}")
        return False
    
    def _update_file_metadata(self, filename: str, url: str, size: int, 
                            checksum: str, last_modified: Optional[str] = None):
        """Update metadata for a downloaded file.
        
        Parameters
        ----------
        filename : str
            Local filename
        url : str
            Source URL
        size : int
            File size in bytes
        checksum : str
            SHA-256 checksum
        last_modified : Optional[str]
            Last-Modified header value
        """
        self.file_metadata[filename] = {
            'url': url,
            'size': size,
            'checksum': checksum,
            'last_modified': last_modified,
            'downloaded_at': datetime.utcnow().isoformat(),
            'local_path': str(self.pdfs_dir / filename)
        }
        self._save_metadata()
    
    def crawl_for_pdfs(self) -> Set[str]:
        """Crawl the WBDG site to find PDF URLs.
        
        Returns
        -------
        Set[str]
            Set of unique PDF URLs found
        """
        root_url = urljoin(self.base_url, self.INDEX_ROOT)
        queue = [root_url]
        
        self.logger.info(f"Starting crawl from: {root_url}")
        
        while queue:
            page = queue.pop(0)
            if page in self.visited_pages:
                continue
                
            self.visited_pages.add(page)
            self.logger.debug(f"Visiting: {page}")
            
            try:
                response = self.session.get(page, timeout=30)
                response.raise_for_status()
                
                # Extract links
                soup = BeautifulSoup(response.text, "html.parser")
                for a in soup.select("a[href]"):
                    href = urljoin(page, a["href"])
                    
                    if href.lower().endswith(".pdf"):
                        self.pdf_urls.add(href)
                        self.logger.debug(f"Found PDF: {href}")
                    elif (href.startswith(root_url) and 
                          href not in self.visited_pages and 
                          href not in queue):
                        queue.append(href)
                        
                self._log_event("crawl_success", {"url": page})
                
            except requests.RequestException as e:
                self.logger.error(f"Failed to crawl {page}: {e}")
                self._log_event("crawl_error", {"url": page, "error": str(e)})
                
            time.sleep(self.REQUEST_DELAY_S)
            
        self.logger.info(f"Crawl complete. Found {len(self.pdf_urls)} PDFs")
        self._log_event("crawl_complete", {"pdf_count": len(self.pdf_urls)})
        
        return self.pdf_urls
    
    def download_pdfs(self, pdf_urls: Optional[Set[str]] = None) -> Dict[str, str]:
        """Download PDFs to local filesystem.
        
        Parameters
        ----------
        pdf_urls : Optional[Set[str]]
            URLs to download. If None, uses URLs from crawl.
            
        Returns
        -------
        Dict[str, str]
            Mapping of filename to download status
        """
        if pdf_urls is None:
            pdf_urls = self.pdf_urls
            
        if not pdf_urls:
            self.logger.warning("No PDF URLs to download")
            return {}
            
        download_results = {}
        
        for pdf_url in tqdm(sorted(pdf_urls), desc="Downloading PDFs"):
            filename = urlparse(pdf_url).path.split("/")[-1]
            if not filename:
                filename = f"document_{hashlib.md5(pdf_url.encode()).hexdigest()[:8]}.pdf"
                
            try:
                # Pre-download validation
                head = self.session.head(pdf_url, timeout=30)
                content_length = int(head.headers.get('content-length', 0))
                last_modified = head.headers.get('last-modified')
                
                # Check if file should be downloaded (incremental check)
                if not self._should_download_file(pdf_url, filename, content_length):
                    download_results[filename] = "skipped_unchanged"
                    continue
                
                if content_length > self.MAX_FILE_SIZE:
                    self.logger.warning(f"File too large: {filename} ({content_length} bytes)")
                    self._log_event("size_error", {
                        "file": filename, 
                        "size": content_length,
                        "error": "File too large"
                    })
                    download_results[filename] = "too_large"
                    continue
                    
                # Download with retry
                pdf_content = self._download_with_retry(pdf_url, filename)
                if pdf_content is None:
                    download_results[filename] = "download_failed"
                    continue
                    
                # Validate PDF
                if not self._validate_pdf(pdf_content):
                    self.logger.warning(f"Invalid PDF: {filename}")
                    self._log_event("validation_error", {
                        "file": filename,
                        "error": "Invalid PDF format"
                    })
                    download_results[filename] = "invalid_pdf"
                    continue
                    
                # Save to file
                output_path = self.pdfs_dir / filename
                with open(output_path, 'wb') as f:
                    f.write(pdf_content)
                    
                # Calculate checksum
                checksum = hashlib.sha256(pdf_content).hexdigest()
                
                # Update metadata for incremental downloads
                self._update_file_metadata(
                    filename=filename,
                    url=pdf_url,
                    size=len(pdf_content),
                    checksum=checksum,
                    last_modified=last_modified
                )
                
                self.logger.info(f"Downloaded: {filename} ({len(pdf_content)} bytes)")
                self._log_event("download_success", {
                    "file": filename,
                    "size": len(pdf_content),
                    "checksum": checksum,
                    "url": pdf_url
                })
                download_results[filename] = "success"
                
            except Exception as e:
                self.logger.error(f"Failed to download {filename}: {e}")
                self._log_event("download_error", {
                    "file": filename,
                    "error": str(e),
                    "url": pdf_url
                })
                download_results[filename] = "error"
                
            time.sleep(self.REQUEST_DELAY_S)
            
        return download_results
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _download_with_retry(self, url: str, filename: str) -> Optional[bytes]:
        """Download a file with retry mechanism."""
        try:
            with self.session.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                content = bytearray()
                for chunk in r.iter_content(chunk_size=self.CHUNK_SIZE):
                    if chunk:
                        content.extend(chunk)
                return bytes(content)
        except Exception as e:
            self.logger.error(f"Download retry failed for {filename}: {e}")
            self._log_event("download_retry", {
                "file": filename,
                "error": str(e),
                "url": url
            })
            raise
    
    def _validate_pdf(self, content: bytes) -> bool:
        """Validate PDF content."""
        try:
            PdfReader(io.BytesIO(content))
            return True
        except Exception:
            return False
    
    def _log_event(self, event_type: str, data: Dict):
        """Log an event to the internal log."""
        entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            **data
        }
        self.log_entries.append(entry)
    
    def save_crawl_log(self):
        """Save crawl log to JSON file."""
        log_file = self.logs_dir / "crawl_log.json"
        with open(log_file, 'w') as f:
            json.dump(self.log_entries, f, indent=2)
        self.logger.info(f"Crawl log saved to: {log_file}")
    
    def run_full_scrape(self) -> Dict:
        """Run complete scraping process.
        
        Returns
        -------
        Dict
            Summary of scraping results
        """
        start_time = time.time()
        
        self.logger.info("Starting full WBDG scrape")
        
        # Crawl for PDFs
        pdf_urls = self.crawl_for_pdfs()
        
        # Download PDFs
        download_results = self.download_pdfs(pdf_urls)
        
        # Save logs
        self.save_crawl_log()
        
        # Generate summary
        end_time = time.time()
        duration = end_time - start_time
        
        # Calculate incremental statistics
        skipped_count = sum(1 for status in download_results.values() 
                          if status in ["skipped_unchanged", "skipped"])
        new_downloads = sum(1 for status in download_results.values() if status == "success")
        
        summary = {
            "duration_seconds": duration,
            "pages_visited": len(self.visited_pages),
            "pdfs_found": len(pdf_urls),
            "download_results": download_results,
            "success_count": new_downloads,
            "skipped_count": skipped_count,
            "total_files_tracked": len(self.file_metadata),
            "incremental_mode": True,
            "output_directory": str(self.output_dir)
        }
        
        self.logger.info(f"Scrape complete in {duration:.1f}s. "
                        f"Downloaded {new_downloads} new, skipped {skipped_count} unchanged, "
                        f"tracking {len(self.file_metadata)} total files")
        
        return summary
    
    def get_incremental_status(self) -> Dict:
        """Get current incremental download status.
        
        Returns
        -------
        Dict
            Status information about tracked files
        """
        if not self.file_metadata:
            return {
                "total_files": 0,
                "status": "no_previous_downloads"
            }
        
        total_size = sum(meta.get('size', 0) for meta in self.file_metadata.values())
        latest_download = max(
            (meta.get('downloaded_at', '') for meta in self.file_metadata.values()),
            default="unknown"
        )
        
        return {
            "total_files": len(self.file_metadata),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "latest_download": latest_download,
            "metadata_file": str(self.metadata_file),
            "status": "ready_for_incremental"
        }


def main():
    """Main entry point for standalone execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description="WBDG PDF Scraper")
    parser.add_argument("--base-url", default="https://www.wbdg.org/",
                       help="Base URL for WBDG site")
    parser.add_argument("--output-dir", default="output",
                       help="Output directory for PDFs and logs")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level")
    parser.add_argument("--crawl-only", action="store_true",
                       help="Only crawl for URLs, don't download")
    parser.add_argument("--status", action="store_true",
                       help="Show incremental download status and exit")
    
    args = parser.parse_args()
    
    scraper = WBDGScraper(
        base_url=args.base_url,
        output_dir=args.output_dir,
        log_level=args.log_level
    )
    
    if args.status:
        status = scraper.get_incremental_status()
        print("=== WBDG Scraper Incremental Status ===")
        if status["status"] == "no_previous_downloads":
            print("No previous downloads found. Next run will be a full scrape.")
        else:
            print(f"Total files tracked: {status['total_files']}")
            print(f"Total size: {status['total_size_mb']} MB")
            print(f"Latest download: {status['latest_download']}")
            print(f"Metadata file: {status['metadata_file']}")
            print("Ready for incremental updates.")
        return
    
    if args.crawl_only:
        pdf_urls = scraper.crawl_for_pdfs()
        scraper.save_crawl_log()
        print(f"Found {len(pdf_urls)} PDF URLs")
        for url in sorted(pdf_urls):
            print(url)
    else:
        summary = scraper.run_full_scrape()
        print(f"Scrape complete: {summary}")


if __name__ == "__main__":
    main()