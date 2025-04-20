import requests
from transforms.api import transform, Output
from transforms.external.systems import external_systems, Source
import pandas as pd
from bs4 import BeautifulSoup

@external_systems(
    wbdg_source=Source("ri.magritte..source.788a5383-dc87-44e9-9e69-a956a548f26b")
)
@transform(
    connection_test_output=Output("ri.foundry.main.dataset.58db10e7-d87c-4f20-a0e8-3388260681d4")
)
def test_connection(wbdg_source, connection_test_output):
    url = wbdg_source.get_https_connection().url
    client = wbdg_source.get_https_connection().get_client()
    
    try:
        response = client.get(url, timeout=30)
        response.raise_for_status()
        
        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract the title and a sample of the text content
        title = soup.title.string if soup.title else "No title found"
        sample_text = soup.get_text()[:500]  # Get first 500 characters of text content
        
        result = {
            "status": "success",
            "url": url,
            "status_code": response.status_code,
            "content_length": len(response.content),
            "title": title,
            "sample_text": sample_text
        }
        print(f"Successfully connected to {url}")
        print(f"Status code: {response.status_code}")
        print(f"Content length: {len(response.content)} bytes")
        print(f"Title: {title}")
        print(f"Sample text: {sample_text[:100]}...")  # Print first 100 characters of sample text
    except requests.exceptions.RequestException as e:
        result = {
            "status": "failure",
            "url": url,
            "error": str(e)
        }
        print(f"Failed to connect to {url}")
        print(f"Error: {str(e)}")

    connection_test_output.write_dataframe(pd.DataFrame([result]))