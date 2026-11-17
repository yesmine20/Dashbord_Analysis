
from pythonnet import load

# Utiliser le runtime .NET Framework de Windows
load("netfx")

import clr

# Charger la bibliothèque ADOMD.NET
dll_path = (
    r"C:\Windows\Microsoft.NET\assembly\GAC_MSIL"
    r"\Microsoft.AnalysisServices.AdomdClient"
    r"\v4.0_15.0.0.0__89845dcd8080cc91"
    r"\Microsoft.AnalysisServices.AdomdClient.dll"
)

clr.AddReference(dll_path)

from Microsoft.AnalysisServices.AdomdClient import AdomdConnection

# Paramètres de connexion Power BI Desktop
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
    print("Connexion au modèle Power BI...")

    connection.Open()
    print("Connexion réussie !")

    command = connection.CreateCommand()
    command.CommandText = query

    reader = command.ExecuteReader()

    print("\nRésultats DAX :")
    print("-" * 65)

    for i in range(reader.FieldCount):
        print(reader.GetName(i), end="\t")

    print()

    count = 0

    while reader.Read() and count < 10:
        print(
            reader.GetValue(0),
            reader.GetValue(1),
            reader.GetValue(2),
            sep="\t"
        )
        count += 1

    reader.Close()
    print("\nTest terminé avec succès.")

finally:
    connection.Close()
