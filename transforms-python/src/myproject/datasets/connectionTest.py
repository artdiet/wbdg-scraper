import requests
from transforms.api import transform, Output
from transforms.external.systems import external_systems, Source
import pandas as pd
from bs4 import BeautifulSoup
from pyspark.sql import SparkSession
from tenacity import retry, stop_after_attempt, wait_exponential

@external_systems(
    wbdg_source=Source("ri.magritte..source.788a5383-dc87-44e9-9e69-a956a548f26b")
)
@transform(
    connection_test_output=Output("ri.foundry.main.dataset.58db10e7-d87c-4f20-a0e8-3388260681d4")
)
def test_connection(wbdg_source, connection_test_output):
    """
    Lightweight connection test for WBDG external system.
    - Fetches the root page only (no crawling or downloads)
    - Uses retry logic for robust error handling
    - Outputs status, URL, status code, content length, title, and sample text
    """
    url = wbdg_source.get_https_connection().url
    client = wbdg_source.get_https_connection().get_client()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
    def fetch_page():
        response = client.get(url, timeout=30)
        response.raise_for_status()
        return response

    try:
        response = fetch_page()
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.title.string if soup.title else "No title found"
        sample_text = soup.get_text()[:500]  # First 500 characters
        result = {
            "status": "success",
            "url": url,
            "status_code": response.status_code,
            "content_length": len(response.content),
            "title": str(title),
            "sample_text": sample_text
        }
        print(f"Successfully connected to {url}")
        print(f"Status code: {response.status_code}")
        print(f"Content length: {len(response.content)} bytes")
        print(f"Title: {title}")
        print(f"Sample text: {sample_text[:100]}...")
    except Exception as e:
        result = {
            "status": "failure",
            "url": url,
            "error": str(e),
            "title": "",
            "sample_text": ""
        }
        print(f"Failed to connect to {url}")
        print(f"Error: {str(e)}")

    # Create a pandas DataFrame
    pandas_df = pd.DataFrame([result])
    # Convert pandas DataFrame to PySpark DataFrame
    spark = SparkSession.builder.getOrCreate()
    spark_df = spark.createDataFrame(pandas_df)
    # Write the PySpark DataFrame to the output
    connection_test_output.write_dataframe(spark_df)