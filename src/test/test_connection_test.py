from unittest.mock import MagicMock
from myproject.datasets.connectionTest import test_connection
import pandas as pd

def test_connection_success(monkeypatch):
    # Mock the external system's HTTPS connection and client
    mock_source = MagicMock()
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = b"<html><title>Test Title</title><body>Hello World!</body></html>"
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_client.get.return_value = mock_response
    mock_source.get_https_connection.return_value.get_client.return_value = mock_client
    mock_source.get_https_connection.return_value.url = "https://www.example.com/"

    # Mock the Output object
    mock_output = MagicMock()

    # Run the test_connection function
    test_connection(mock_source, mock_output)

    # Check that write_dataframe was called
    assert mock_output.write_dataframe.called
    # Optionally, check the DataFrame contents
    args, kwargs = mock_output.write_dataframe.call_args
    df = args[0]
    assert "status" in df.columns
    assert "url" in df.columns
    assert isinstance(df, pd.DataFrame) or hasattr(df, 'count')


def test_connection_failure(monkeypatch):
    # Mock the external system's HTTPS connection and client to raise an error
    mock_source = MagicMock()
    mock_client = MagicMock()
    mock_client.get.side_effect = Exception("Connection failed")
    mock_source.get_https_connection.return_value.get_client.return_value = mock_client
    mock_source.get_https_connection.return_value.url = "https://www.example.com/"

    # Mock the Output object
    mock_output = MagicMock()

    # Run the test_connection function
    test_connection(mock_source, mock_output)

    # Check that write_dataframe was called
    assert mock_output.write_dataframe.called
    args, kwargs = mock_output.write_dataframe.call_args
    df = args[0]
    assert "status" in df.columns
    # Should have at least one row with status 'failure'
    if hasattr(df, 'filter'):
        # PySpark DataFrame
        assert df.filter(df.status == "failure").count() >= 1
    else:
        # Pandas DataFrame
        assert (df['status'] == "failure").any() 