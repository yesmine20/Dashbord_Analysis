from src.powerbi import get_analysis_data

print("Test de récupération des données Power BI...")

df = get_analysis_data()

print("\nExtraction réussie !")
print("Dimensions :", df.shape)

print("\nPremières lignes :")
print(df.head(10).to_string(index=False))

print("\nPériode :")
print("Début :", df["date"].min())
print("Fin   :", df["date"].max())

print("\nValeurs manquantes :")
print(df.isna().sum())

print("\nColonnes :")
print(df.columns.tolist())