from src.powerbi import query_dax, ANALYSIS_DAX

print("TEST 1 : requête mensuelle simple")

simple_query = """
EVALUATE
SUMMARIZECOLUMNS(
    'Date'[Month],
    "Orders", [Orders],
    "Sales", [Sales]
)
ORDER BY 'Date'[Month]
"""

df_simple = query_dax(simple_query)

print("Dimensions :", df_simple.shape)
print(df_simple.head(5).to_string(index=False))
print("Types :")
print(df_simple.dtypes)


print("\nTEST 2 : requête complète du projet")

df_full = query_dax(ANALYSIS_DAX)

print("Dimensions :", df_full.shape)
print("Colonnes :", df_full.columns.tolist())
print(df_full.head(10).to_string(index=False))

if not df_full.empty:
    print("\nTypes des valeurs de la première ligne :")
    for column in df_full.columns:
        value = df_full.iloc[0][column]
        print(column, ":", repr(value), "|", type(value))