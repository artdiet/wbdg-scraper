import requests
from transforms.api import transform, Output
from transforms.external.systems import external_systems, Source
import pandas as pd
from bs4 import BeautifulSoup
from pyspark.sql import SparkSession

@external_systems(
    wbdg_source=Source("ri.magritte..source.788a5383-dc87-44e9-9e69-a956a548f26b")
)
@transform(
    connection_test_output=Output("ri.foundry.main.dataset.58db10e7-d87c-4f20-a0e8-3388260681d4")
)
def test_connection(wbdg_source, connection_test_output):
    # ... (rest of your code remains the same)

    # Create a pandas DataFrame
    pandas_df = pd.DataFrame([result])

    # Convert pandas DataFrame to PySpark DataFrame
    spark = SparkSession.builder.getOrCreate()
    spark_df = spark.createDataFrame(pandas_df)

    # Write the PySpark DataFrame to the output
    connection_test_output.write_dataframe(spark_df)