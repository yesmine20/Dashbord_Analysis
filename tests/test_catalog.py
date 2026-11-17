from pythonnet import load
load("netfx")

import clr

dll_path = (
    r"C:\Windows\Microsoft.NET\assembly\GAC_MSIL"
    r"\Microsoft.AnalysisServices.AdomdClient"
    r"\v4.0_15.0.0.0__89845dcd8080cc91"
    r"\Microsoft.AnalysisServices.AdomdClient.dll"
)

clr.AddReference(dll_path)

from Microsoft.AnalysisServices.AdomdClient import AdomdConnection

connection_string = "Data Source=localhost:22373;"

connection = AdomdConnection(connection_string)

try:
    print("Connexion au serveur Power BI...")
    connection.Open()
    print("Connexion réussie !")

    command = connection.CreateCommand()

    command.CommandText = """
    SELECT
        [CATALOG_NAME],
        [DATABASE_ID]
    FROM $SYSTEM.DBSCHEMA_CATALOGS
    """

    reader = command.ExecuteReader()

    print("\nCatalogues disponibles :")

    while reader.Read():
        print("Nom :", reader.GetValue(0))
        print("ID  :", reader.GetValue(1))
        print("-" * 40)

    reader.Close()

finally:
    connection.Close()