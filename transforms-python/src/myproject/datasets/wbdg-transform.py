import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from transforms.api import transform
from transforms.mediasets import MediaSetOutput
from transforms.external.systems import external_systems, Source

REQUEST_DELAY = 0.25  # seconds between HTTP requests

@external_systems(
    wbdg_source=Source("ri.magritte..source.788a5383-dc87-44e9-9e69-a956a548f26b")
)
@transform(
    wbdg_pdfs=MediaSetOutput(
        "ri.mio.main.media-set.b201835c-6898-44f3-9d5f-77162fdca7c5"
    )
)
def compute(wbdg_source, wbdg_pdfs):
    """
    Crawl the WBDG UFC index and stream every PDF into a media dataset.
    The first successful build creates the media set; subsequent builds
    add only new or updated files (idempotent).
    """
    url = wbdg_source.get_https_connection().url
    client = wbdg_source.get_https_connection().get_client()

    # ---------- 1. Discover all PDF URLs in the UFC section ----------
    visited, queue, pdf_urls = set(), [url], set()

    while queue:
        page = queue.pop()
        if page in visited:
            continue
        visited.add(page)

        retries = 3
        for attempt in range(retries):
            try:
                response = client.get(page, timeout=30)
                response.raise_for_status()
                html = response.text
                break
            except requests.exceptions.RequestException:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise

        soup = BeautifulSoup(html, "html.parser")

        for a in soup.select("a[href]"):
            href = urljoin(page, a["href"])
            if href.lower().endswith(".pdf"):
                pdf_urls.add(href)
            elif href.startswith(url) and href not in visited:
                queue.append(href)

        time.sleep(REQUEST_DELAY)

    # ---------- 2. Upload each PDF to the media set ----------
    for pdf_url in sorted(pdf_urls):
        filename = urlparse(pdf_url).path.split("/")[-1]

        # Skip if the exact path already exists (makes rebuilds cheap)
        if wbdg_pdfs.media_item_exists_by_path(filename):
            continue

        response = client.get(pdf_url, stream=True, timeout=60)
        response.raise_for_status()
        wbdg_pdfs.put_media_item(response.raw, filename)

        time.sleep(REQUEST_DELAY)