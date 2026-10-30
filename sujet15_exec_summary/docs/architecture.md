# Architecture

```
Power BI (AdventureWorks_Sales.pbix)
   |  export "Données résumées" (1 visuel Tableau)
   v
data/export_kpi_mensuel.csv
   |  src/load_data.py      nettoyage, contrôle des totaux vs rapport Power BI
   v
src/detect.py               5 règles déterministes (aucun LLM)  ->  JSON standardisé
   |
   v
outputs/<scenario>_input.json   <- SEULE entrée du LLM
   |  src/prompts.py + src/llm_client.py
   v
Texte (Executive Summary + anomalies expliquées)
   |  src/check_numbers.py   chaque chiffre du texte doit exister dans le JSON
   v
Brouillon IA (Markdown, statut "AI DRAFT")
   |  src/validate.py ou app.py   relecture humaine + checklist
   v
Rapport VALIDATED / NEEDS REVISION  (+ outputs/validation_log.csv)
```

## Qui fait quoi

| Bloc | Rôle | Garde-fou |
|---|---|---|
| Moteur de détection | calcule KPI, variations, écarts, contributions par segment | aucun LLM, résultats reproductibles |
| LLM | met le JSON en récit | prompt système : uniquement le JSON, sinon "No data available"; "facteurs possibles", jamais "causes" |
| Contrôle automatique | extrait les nombres du texte et les cherche dans le JSON | signale les chiffres inventés |
| Validation humaine | relit, corrige, approuve | statut visible sur le rapport |

## Garde-fous dans le code (pas seulement dans le prompt)

- Périmètre vide ou valeur de filtre inconnue (ex. région "Germany", année 2023) : le JSON porte `status: "no_data"` et le
  pipeline renvoie "No data available" **sans appeler le LLM**.
- Les années partielles (2017 = juillet-décembre, 2020 = janvier-juin) sont déclarées dans `limitations`, et la comparaison
  annuelle se fait sur une fenêtre équivalente (règle R3).
- Les commandes (`Orders`) ne sont pas additives d'une ligne à l'autre : elles sont exclues.
