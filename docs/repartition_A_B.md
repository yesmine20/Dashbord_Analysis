# Répartition du travail à trois

| Élève | Responsabilités principales | Livrables de travail |
|---|---|---|
| A — Données et Power BI | Décrire l’export, contrôler les totaux et les dimensions, vérifier les règles métier et les limites des données. | `data/`, `src/load_data.py`, référence Power BI, contrôle des données. |
| B — Analyse et anomalies | Expliquer les KPI, les cinq règles et les seuils; concevoir les scénarios et renseigner la matrice de recette. | `src/detect.py`, `src/config.py`, `scenarios/`, `docs/rules.md`, `scenarios/ground_truth.csv`. |
| C — IA et restitution | Configurer le fournisseur LLM, examiner les prompts et contrôles, conduire la validation humaine et préparer la démonstration. | `src/prompts.py`, `src/llm_client.py`, `app.py`, rapports et présentation. |

Les trois élèves relisent le rapport final. Pour limiter l’auto-évaluation, la personne qui valide une réponse ne devrait pas être la seule à l’avoir générée ou à avoir rédigé le prompt.

## Jalons

1. A confirme la provenance, les mesures et les totaux du fichier exporté.
2. B produit le JSON d’un scénario et justifie les alertes détectées.
3. C génère le résumé, montre le JSON transmis et consigne le contrôle humain.
4. L’équipe complète la matrice de recette avec des sorties du vrai modèle testé et présente les limites.
