"""
Copyright © 2025 DTRIQ LLC. All rights reserved.

WBDG UFC PDF Scraper — Palantir Foundry Lightweight Transform
============================================================
This transform crawls the Whole Building Design Guide (WBDG) Unified Facilities
Criteria site (https://www.wbdg.org/dod/ufc) and copies every publicly linked
PDF into a Foundry *media dataset*.  Downstream transforms can OCR the PDFs,
parse text, or simply make them searchable in Workshop.

Key design goals
----------------
1. **Network safety**  – All outbound HTTP traffic routes through an
   *External System* (ri.magritte..source.…).  Egress is limited to wbdg.org.
2. **Lightweight profile** – Runs in a single container; no Spark job spin‑up.
3. **Idempotent** – Re‑runs simply re‑upload a PDF if the filename already
   exists (Foundry versions media items in‑place).
4. **Debug‑friendly** – Writes a crawl log table (`crawl_log`) so failures are
   visible without digging through build logs.

External Python deps (add to ``requirements.txt``)
-------------------------------------------------
• requests==2.31.0    # robust HTTP client
• beautifulsoup4==4.12.3 # HTML parsing

Foundry library (install once via **Libraries** UI)
--------------------------------------------------
• transforms‑media      # MediaSetOutputParam helpers

Outputs
-------
* ``wbdg_pdfs`` – MediaSetOutput (PDF binaries)
* ``crawl_log`` – Output (Spark table) — one row per crawler event
"""

from __future__ import annotations

import io
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from transforms.api import transform, Output
from transforms.mediasets import MediaSetOutput
from transforms.external.systems import external_systems, Source

###############################################################################
# CONFIGURATION CONSTANTS
# ---------------------------------------------------------------------------
# • ``INDEX_ROOT`` is the path segment that contains the UFC catalogue.
# • ``REQUEST_DELAY_S`` throttles the crawler so we do ~4 req/s max — courteous
#   to the public server and low risk of triggering site‑rate‑limit rules.
###############################################################################
INDEX_ROOT = "dod/ufc"   # e.g. https://www.wbdg.org/dod/ufc
REQUEST_DELAY_S = 0.25    # seconds between HTTP requests

###############################################################################
# TRANSFORM DEFINITION (decorators)
# ---------------------------------------------------------------------------
# 1. ``@external_systems`` gives us a *typed* handle to the outbound HTTP
#    connection defined in Foundry’s *External Systems* catalog.
# 2. ``@transform`` declares two outputs:
#      • ``wbdg_pdfs``  (MediaSetOutput)  – binary PDF files
#      • ``crawl_log``  (Output)          – Spark table summarising the build
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
# pylint: disable=too-many-locals,too-many-branches

def compute(wbdg_source, wbdg_pdfs, crawl_log):
    """Entry point run by the Foundry build engine."""

    # ---------------------------------------------------------------------
    # Stage 0  — Create an HTTP client that respects Foundry egress settings.
    # ---------------------------------------------------------------------
    base_url: str = wbdg_source.get_https_connection().url.rstrip("/") + "/"
    client = wbdg_source.get_https_connection().get_client()

    # Build the absolute URL for the UFC root index.
    root_url: str = urljoin(base_url, INDEX_ROOT)

    # ---------------------------------------------------------------------
    # Stage 1  — Crawl the UFC website collecting *every* PDF URL.
    # ---------------------------------------------------------------------
    visited_pages: set[str] = set()  # keeps us from re‑visiting pages
    queue: list[str] = [root_url]    # DFS / BFS frontier (order doesn’t matter)
    pdf_urls: set[str] = set()       # unique HTTPS links ending in “.pdf”

    # Each dict in ``log_rows`` becomes one row in the crawl_log Spark table.
    log_rows: list[dict] = []

    while queue:
        page: str = queue.pop()
        if page in visited_pages:
            continue
        visited_pages.add(page)

        # --- Fetch the HTML ------------------------------------------------
        try:
            response = client.get(page, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            # Capture network errors without failing the whole build.
            log_rows.append({"stage": "crawl_error", "url": page, "error": str(exc)})
            continue  # skip to next page in the queue

        # --- Parse links with BeautifulSoup -------------------------------
        soup = BeautifulSoup(response.text, "html.parser")

        for a in soup.select("a[href]"):
            href: str = urljoin(page, a["href"])

            if href.lower().endswith(".pdf"):
                pdf_urls.add(href)
            # Recurse only within the UFC subtree so we don’t spider the entire
            # WBDG site.
            elif href.startswith(root_url) and href not in visited_pages:
                queue.append(href)

        time.sleep(REQUEST_DELAY_S)  # politeness throttle

    # Record crawl summary.
    log_rows.append({"stage": "crawl_complete", "pdf_count": len(pdf_urls)})

    # Early‑return safeguard: nothing found or site unreachable.
    if not pdf_urls:
        _write_log(crawl_log, log_rows)
        return

    # ---------------------------------------------------------------------
    # Stage 2  — Upload each PDF directly into the media set.
    # ---------------------------------------------------------------------
    # NOTE: We *don’t* try to de‑duplicate via list_media_paths(); older SDK
    # versions lack that helper.  Put‑media always works — Foundry versions
    # items by path behind the scenes.

    for pdf_url in sorted(pdf_urls):
        filename: str = urlparse(pdf_url).path.split("/")[-1]  # "UFC_1_101_01.pdf"

        try:
            # Stream the file; keep memory use low.
            with client.get(pdf_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                # Wrap bytes in BytesIO so ``put_media_item`` has a seekable
                # file‑like object (required by the API).
                wbdg_pdfs.put_media_item(io.BytesIO(r.content), filename)
                log_rows.append({"stage": "upload_ok", "file": filename})
        except Exception as exc:  # noqa: BLE001 — broad catch is acceptable here
            log_rows.append({"stage": "upload_error", "file": filename, "error": str(exc)})

        time.sleep(REQUEST_DELAY_S)

    # ---------------------------------------------------------------------
    # Stage 3  — Persist the crawl log for observability.
    # ---------------------------------------------------------------------
    _write_log(crawl_log, log_rows)


###############################################################################
# HELPER FUNCTIONS
###############################################################################

def _write_log(ds_output, rows):
    """Convert ``rows`` (list[dict]) to a Spark DataFrame and write it out.

    Parameters
    ----------
    ds_output : OutputParam
        The tabular dataset declared as ``crawl_log`` in the @transform.
    rows : list[dict]
        Each dict becomes one row; keys are column names.
    """

    import pandas as pd
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    pdf = pd.DataFrame(rows)
    spark_df = spark.createDataFrame(pdf)  # pandas → Spark (type inference)
    ds_output.write_dataframe(spark_df)
