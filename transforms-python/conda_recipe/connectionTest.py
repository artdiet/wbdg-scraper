import requests
from transforms.api import transform
from transforms.external.systems import external_systems, Source

@external_systems(
    wbdg_source=Source("ri.magritte..source.788a5383-dc87-44e9-9e69-a956a548f26b")
)
@transform()
def test_connection(wbdg_source):
    url = wbdg_source.get_https_connection().url
    client = wbdg_source.get_https_connection().get_client()
    
    try:
        response = client.get(url, timeout=30)
        response.raise_for_status()
        print(f"Successfully connected to {url}")
        print(f"Status code: {response.status_code}")
        print(f"Content length: {len(response.content)} bytes")
    except requests.exceptions.RequestException as e:
        print(f"Failed to connect to {url}")
        print(f"Error: {str(e)}")

    return {}