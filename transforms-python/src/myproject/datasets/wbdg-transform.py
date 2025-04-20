# transforms/wbdg_scraper.py
#
# Scrapes the WBDG UFC site and uploads every PDF into a Foundry media set.
# 3rd‑party deps: requests, beautifulsoup4  (add to requirements.txt)
#
# NOTE: Install the “transforms‑media” library in this repo once.
#       Libraries drawer  ➞  search “transforms-media” ➞  Install.

import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from transforms.api import transform, lightweight
from transforms.mediasets import MediaSetOutput, LightweightMediaSetOutputParam

INDEX_URL = "https://www.wbdg.org/dod/ufc"
REQUEST_DELAY = 0.25  # seconds between HTTP requests


@lightweight(should_snapshot=True)
@transform(
    wbdg_pdfs=MediaSetOutput(
        "ri.mio.main.media-set.b201835c-6898-44f3-9d5f-77162fdca7c5"
    )
)
def compute(wbdg_pdfs: LightweightMediaSetOutputParam):
    """
    Crawl the WBDG UFC index and stream every PDF into a media dataset.
    The first successful build creates the media set; subsequent builds
    add only new or updated files (idempotent).
    """
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "foundry-wbdg-scraper/1.0 (https://wbdg.org)"}
    )

    # ---------- 1. Discover all PDF URLs in the UFC section ----------
    visited, queue, pdf_urls = set(), [INDEX_URL], set()

    while queue:
        page = queue.pop()
        if page in visited:
            continue
        visited.add(page)

        html = session.get(page, timeout=30).text
        soup = BeautifulSoup(html, "html.parser")

        for a in soup.select("a[href]"):
            href = urljoin(page, a["href"])
            if href.lower().endswith(".pdf"):
                pdf_urls.add(href)
            elif href.startswith(INDEX_URL) and href not in visited:
                queue.append(href)

        time.sleep(REQUEST_DELAY)

    # ---------- 2. Upload each PDF to the media set ----------
    for pdf_url in sorted(pdf_urls):
        filename = urlparse(pdf_url).path.split("/")[-1]

        # Skip if the exact path already exists (makes rebuilds cheap)
        if wbdg_pdfs.media_item_exists_by_path(filename):
            continue

        with session.get(pdf_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            wbdg_pdfs.put_media_item(r.raw, filename)

        time.sleep(REQUEST_DELAY)
