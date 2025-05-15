"""
Copyright © 2025 DTRIQ LLC. All rights reserved.

WBDG UFC PDF Scraper — Palantir Foundry Lightweight Transform
============================================================
This transform crawls the Whole Building Design Guide (WBDG) Unified Facilities
Criteria site (https://www.wbdg.org/dod/ufc) and copies every publicly linked
PDF into a Foundry *media dataset*.  Downstream transforms can OCR the PDFs,
parse text, or simply make them searchable in Workshop.

Key design goals
----------------
1. **Network safety**  – All outbound HTTP traffic routes through an
   *External System* (ri.magritte..source.…).  Egress is limited to wbdg.org.
2. **Lightweight profile** – Runs in a single container; no Spark job spin‑up.
3. **Idempotent** – Re‑runs simply re‑upload a PDF if the filename already
   exists (Foundry versions media items in‑place).
4. **Debug‑friendly** – Writes a crawl log table (`crawl_log`) so failures are
   visible without digging through build logs.

External Python deps (add to ``requirements.txt``)
-------------------------------------------------
• requests==2.31.0     # robust HTTP client
• beautifulsoup4==4.12.3 # HTML parsing
• tenacity==8.2.3      # retry mechanism
• tqdm==4.66.1         # progress bars
• PyPDF2==3.0.1        # PDF validation

Foundry library (install once via **Libraries** UI)
--------------------------------------------------
• transforms‑media      # MediaSetOutputParam helpers

Outputs
-------
* ``wbdg_pdfs`` – MediaSetOutput (PDF binaries)
* ``crawl_log`` – Output (Spark table) — one row per crawler event

Error Handling
-------------
The transform implements several layers of error handling:
1. Network errors: Retries with exponential backoff
2. File validation: Size checks and PDF format validation
3. Resource management: Chunked downloads and memory limits
4. Logging: Detailed error tracking in crawl_log

Performance Considerations
-------------------------
- Rate limiting: 0.25s delay between requests
- Chunk size: 8KB for memory-efficient downloads
- Max file size: 100MB to prevent resource exhaustion
- Retry strategy: 3 attempts with exponential backoff
"""

from __future__ import annotations

import io
import time
import hashlib
from urllib.parse import urljoin, urlparse
from typing import Optional

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm
from PyPDF2 import PdfReader
from transforms.api import transform, Output
from transforms.mediasets import MediaSetOutput
from transforms.external.systems import external_systems, Source

###############################################################################
# CONFIGURATION CONSTANTS
###############################################################################
# Base URL path for the UFC catalog
INDEX_ROOT = "dod/ufc"   # e.g. https://www.wbdg.org/dod/ufc

# Rate limiting to be courteous to the server
REQUEST_DELAY_S = 0.25    # seconds between HTTP requests

# Retry configuration for failed downloads
MAX_RETRIES = 3          # maximum number of retry attempts

# Resource management settings
CHUNK_SIZE = 8192        # bytes to read at a time (8KB)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB maximum file size

###############################################################################
# TRANSFORM DEFINITION
###############################################################################
@external_systems(
    wbdg_source=Source("ri.magritte..source.788a5383-dc87-44e9-9e69-a956a548f26b")
)
@transform(
    wbdg_pdfs=MediaSetOutput(
        "ri.mio.main.media-set.b201835c-6898-44f3-9d5f-77162fdca7c5"
    ),
    crawl_log=Output(
        "/Coordcode-82190b/Engineer Assistant/logic/wbdg_crawl_log"
    ),
)
def compute(wbdg_source, wbdg_pdfs, crawl_log):
    """Entry point run by the Foundry build engine.
    
    This function orchestrates the entire PDF download process:
    1. Initializes the HTTP client with Foundry's external system
    2. Crawls the WBDG site to find PDF links
    3. Downloads and validates each PDF
    4. Uploads valid PDFs to Foundry
    5. Logs all activities for monitoring
    
    Parameters
    ----------
    wbdg_source : Source
        Foundry external system for HTTP connections
    wbdg_pdfs : MediaSetOutput
        Foundry media dataset for storing PDFs
    crawl_log : Output
        Foundry dataset for logging crawl activities
    """
    # Initialize HTTP client with Foundry's external system
    base_url: str = wbdg_source.get_https_connection().url.rstrip("/") + "/"
    client = wbdg_source.get_https_connection().get_client()
    root_url: str = urljoin(base_url, INDEX_ROOT)

    # Initialize tracking variables for the crawl
    visited_pages: set[str] = set()  # Track visited pages to avoid cycles
    queue: list[str] = [root_url]    # Pages to visit (BFS)
    pdf_urls: set[str] = set()       # Unique PDF URLs found
    log_rows: list[dict] = []        # Log entries for crawl_log

    # Crawl the site to find PDF links
    while queue:
        page: str = queue.pop()
        if page in visited_pages:
            continue
        visited_pages.add(page)

        # Fetch and parse the page
        try:
            response = client.get(page, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            log_rows.append({
                "stage": "crawl_error",
                "url": page,
                "error": str(exc),
                "retry_count": 0
            })
            continue

        # Extract links from the page
        soup = BeautifulSoup(response.text, "html.parser")
        for a in soup.select("a[href]"):
            href: str = urljoin(page, a["href"])
            if href.lower().endswith(".pdf"):
                pdf_urls.add(href)
            elif href.startswith(root_url) and href not in visited_pages:
                queue.append(href)

        time.sleep(REQUEST_DELAY_S)  # Rate limiting

    # Log crawl completion
    log_rows.append({"stage": "crawl_complete", "pdf_count": len(pdf_urls)})

    if not pdf_urls:
        _write_log(crawl_log, log_rows)
        return

    # Download and validate each PDF
    for pdf_url in tqdm(sorted(pdf_urls), desc="Downloading PDFs"):
        filename: str = urlparse(pdf_url).path.split("/")[-1]
        
        try:
            # Pre-download validation
            head = client.head(pdf_url, timeout=30)
            content_length = int(head.headers.get('content-length', 0))
            
            if content_length > MAX_FILE_SIZE:
                log_rows.append({
                    "stage": "size_error",
                    "file": filename,
                    "size": content_length,
                    "error": "File too large"
                })
                continue

            # Download with retry mechanism
            pdf_content = _download_with_retry(client, pdf_url, filename, log_rows)
            if pdf_content is None:
                continue

            # Validate PDF format
            if not _validate_pdf(pdf_content):
                log_rows.append({
                    "stage": "validation_error",
                    "file": filename,
                    "error": "Invalid PDF format"
                })
                continue

            # Calculate checksum for integrity verification
            checksum = hashlib.sha256(pdf_content).hexdigest()
            
            # Upload to Foundry
            wbdg_pdfs.put_media_item(io.BytesIO(pdf_content), filename)
            log_rows.append({
                "stage": "upload_ok",
                "file": filename,
                "size": content_length,
                "checksum": checksum
            })

        except Exception as exc:
            log_rows.append({
                "stage": "upload_error",
                "file": filename,
                "error": str(exc)
            })

        time.sleep(REQUEST_DELAY_S)  # Rate limiting

    # Write final log entries
    _write_log(crawl_log, log_rows)

###############################################################################
# HELPER FUNCTIONS
###############################################################################

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def _download_with_retry(client, url: str, filename: str, log_rows: list) -> Optional[bytes]:
    """Download a file with retry mechanism.
    
    Implements exponential backoff retry for failed downloads.
    Uses chunked downloading to manage memory usage.
    
    Parameters
    ----------
    client : requests.Session
        HTTP client for making requests
    url : str
        URL of the file to download
    filename : str
        Name of the file (for logging)
    log_rows : list
        List to append log entries to
    
    Returns
    -------
    Optional[bytes]
        File content if download successful, None otherwise
    """
    try:
        with client.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            content = bytearray()
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    content.extend(chunk)
            return bytes(content)
    except Exception as exc:
        log_rows.append({
            "stage": "download_error",
            "file": filename,
            "error": str(exc),
            "retry_count": getattr(exc, 'retry_count', 0)
        })
        raise

def _validate_pdf(content: bytes) -> bool:
    """Validate PDF content.
    
    Attempts to parse the PDF to verify it's a valid PDF file.
    
    Parameters
    ----------
    content : bytes
        PDF file content to validate
    
    Returns
    -------
    bool
        True if valid PDF, False otherwise
    """
    try:
        PdfReader(io.BytesIO(content))
        return True
    except Exception:
        return False

def _write_log(ds_output, rows):
    """Convert rows to a Spark DataFrame and write it out.
    
    Parameters
    ----------
    ds_output : Output
        Foundry dataset to write to
    rows : list[dict]
        List of dictionaries containing log entries
    """
    import pandas as pd
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    pdf = pd.DataFrame(rows)
    spark_df = spark.createDataFrame(pdf)
    ds_output.write_dataframe(spark_df)
