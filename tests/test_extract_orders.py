
from pythonnet import load
load("netfx")

import clr
import pandas as pd

dll_path = (
    r"C:\Windows\Microsoft.NET\assembly\GAC_MSIL"
    r"\Microsoft.AnalysisServices.AdomdClient"
    r"\v4.0_15.0.0.0__89845dcd8080cc91"
    r"\Microsoft.AnalysisServices.AdomdClient.dll"
)

clr.AddReference(dll_path)

from Microsoft.AnalysisServices.AdomdClient import AdomdConnection

connection_string = (
    "Data Source=localhost:26486;"
    "Initial Catalog=053c49d1-3383-46c3-8d59-51a2ea8e83b0;"
)

query = """
EVALUATE
SUMMARIZECOLUMNS(
    'Date'[Month],
    "Orders", [Orders],
    "Sales", [Sales]
)
ORDER BY
    'Date'[Month]
"""

connection = AdomdConnection(connection_string)

try:
    connection.Open()

    command = connection.CreateCommand()
    command.CommandText = query

    reader = command.ExecuteReader()

    rows = []

    while reader.Read():
        date_value = reader.GetValue(0)

        rows.append({
            "date": pd.Timestamp(
                year=date_value.Year,
                month=date_value.Month,
                day=1
            ),
            "Orders": int(reader.GetValue(1)),
            "Sales": float(reader.GetValue(2))
        })

    reader.Close()

    df = pd.DataFrame(rows)

    print("\nExtraction terminée !")
    print(df.to_string(index=False))
    print("\nNombre de lignes :", len(df))
    print("\nValeurs manquantes :")
    print(df.isna().sum())
finally:
    connection.Close()
