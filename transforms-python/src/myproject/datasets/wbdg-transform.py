import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from transforms.api import transform, Output
from transforms.mediasets import MediaSetOutput
from transforms.external.systems import external_systems, Source
from pyspark.sql import SparkSession
import pandas as pd

REQUEST_DELAY = 0.25  # seconds between HTTP requests

@external_systems(
    wbdg_source=Source("ri.magritte..source.788a5383-dc87-44e9-9e69-a956a548f26b")
)
@transform(
    wbdg_pdfs=MediaSetOutput(
        "ri.mio.main.media-set.b201835c-6898-44f3-9d5f-77162fdca7c5"
    ),
    connection_test_output=Output("/Coordcode-82190b/Engineer Assistant/logic/wbdg_connection_log")
)
def compute(wbdg_source, wbdg_pdfs, connection_test_output):
    """
    Crawl the WBDG UFC index and stream every PDF into a media dataset.
    The first successful build creates the media set; subsequent builds
    add only new or updated files (idempotent).
    """
    base_url = wbdg_source.get_https_connection().url
    client = wbdg_source.get_https_connection().get_client()
    ufc_url = urljoin(base_url, "dod/ufc")

    # Connection test
    try:
        response = client.get(ufc_url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        title = soup.title.string if soup.title else "No title found"
        sample_text = soup.get_text()[:500]  # Get first 500 characters of text content
        
        result = {
            "status": "success",
            "url": ufc_url,
            "status_code": response.status_code,
            "content_length": len(response.content),
            "title": str(title),
            "sample_text": sample_text
        }
        print(f"Successfully connected to {ufc_url}")
        print(f"Status code: {response.status_code}")
        print(f"Content length: {len(response.content)} bytes")
        print(f"Title: {title}")
        print(f"Sample text: {sample_text[:100]}...")
    except requests.exceptions.RequestException as e:
        result = {
            "status": "failure",
            "url": ufc_url,
            "error": str(e),
            "title": "",
            "sample_text": ""
        }
        print(f"Failed to connect to {ufc_url}")
        print(f"Error: {str(e)}")

    # Write connection test results
    pandas_df = pd.DataFrame([result])
    spark = SparkSession.builder.getOrCreate()
    spark_df = spark.createDataFrame(pandas_df)
    connection_test_output.write_dataframe(spark_df)

    # If connection failed, stop here
    if result["status"] == "failure":
        return

    # ---------- 1. Discover all PDF URLs in the UFC section ----------
    visited, queue, pdf_urls = set(), [ufc_url], set()

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
            elif href.startswith(ufc_url) and href not in visited:
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