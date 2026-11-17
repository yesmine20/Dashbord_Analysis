# Résumé technique du projet

## 1. Objectif

Le projet transforme un export mensuel Power BI du rapport **AdventureWorks Sales** en :

- indicateurs KPI ;
- détection automatique d'anomalies ;
- résumé exécutif généré par un LLM ;
- explication des anomalies ;
- contrôle automatique des chiffres ;
- validation humaine ;
- rapport Markdown ou PDF.

Le principe général est : **le code calcule, le LLM rédige, l'humain valide**.

## 2. Architecture générale

```text
Export CSV Power BI
        |
        v
Nettoyage et contrôle des données
        |
        v
Calcul des KPI et détection déterministe
        |
        v
JSON standardisé
        |
        v
Génération du texte par LLM
        |
        v
Vérification des chiffres
        |
        v
Rapport Markdown / PDF
        |
        v
Validation humaine
```

La description détaillée de l'architecture se trouve dans `sujet15_exec_summary/docs/architecture.md`.

## 3. Données utilisées

Le fichier `sujet15_exec_summary/data/export_kpi_mensuel.csv` contient :

- 461 lignes ;
- une période allant de juillet 2017 à juin 2020 ;
- les ventes, coûts, profits et commandes ;
- les catégories de produits ;
- les régions ou groupes ;
- les canaux de vente.

Le module `src/load_data.py` assure :

- la lecture et le nettoyage du CSV ;
- la conversion des montants texte en nombres ;
- la conversion des mois en dates ;
- l'application des filtres ;
- la vérification des totaux avec Power BI ;
- la suppression des lignes sans données financières exploitables.

Les totaux de référence sont définis dans `src/config.py` :

- Sales : environ 109,8 M$ ;
- Cost : environ 97,3 M$ ;
- Profit : environ 12,6 M$.

La mesure `Orders` est conservée dans les données mais exclue des agrégations, car elle n'est pas additive entre les lignes.

## 4. Détection des anomalies

Le moteur `src/detect.py` applique cinq règles déterministes, sans utiliser de LLM.

### R1 - Alerte de marge

Détecte :

- un profit mensuel négatif ;
- ou une marge inférieure d'au moins 5 points à la marge des trois mois précédents.

Les mois dont les ventes sont inférieures à 100 000 $ sont ignorés.

### R2 - Variation mensuelle des ventes

Détecte une hausse ou une baisse lorsque :

- la variation atteint au moins 15 % ;
- et la variation absolue atteint au moins 1 M$.

### R3 - Comparaison annuelle comparable

Compare les six derniers mois disponibles aux mêmes six mois de l'année précédente. Cette règle évite de comparer directement des années partielles.

### R4 - Écart entre canaux

Détecte un écart de marge d'au moins 20 points entre les canaux disponibles, notamment Internet et Reseller.

### R5 - Écart d'un segment

Détecte une catégorie ou une région dont la marge s'écarte d'au moins 10 points de la marge globale, avec un minimum de 1 M$ de ventes.

Les seuils sont centralisés dans `src/config.py` et documentés dans `sujet15_exec_summary/docs/rules.md`.

## 5. Génération par IA

Le LLM ne reçoit pas directement le fichier CSV. Il reçoit uniquement le JSON produit par le moteur d'analyse.

Le module `src/llm_client.py` prend en charge :

- OpenAI ;
- Azure OpenAI ;
- Anthropic ;
- Groq ;
- un mode `mock` hors ligne.

Le mode `mock` permet de tester toute la chaîne sans clé API, mais ne mesure pas la qualité d'un modèle génératif réel.

Les prompts sont définis dans `src/prompts.py`. Ils imposent notamment :

- l'utilisation exclusive des informations du JSON ;
- la conservation exacte des chiffres affichés ;
- l'interdiction d'inventer des causes ;
- l'utilisation de formulations comme « facteurs possibles » ;
- la réponse `No data available` si le périmètre ne contient aucune donnée.

## 6. Garde-fous contre les hallucinations

Le module `src/check_numbers.py` extrait les nombres du texte produit et vérifie qu'ils apparaissent dans le JSON d'entrée.

Il peut détecter :

- un montant inventé ;
- un pourcentage inexistant ;
- une valeur modifiée ou arrondie incorrectement.

Ce contrôle réduit le risque d'hallucination, mais ne vérifie pas entièrement le sens des phrases ni la pertinence métier de l'interprétation.

## 7. Application Streamlit

L'interface est implémentée dans `app.py` avec Streamlit.

Elle permet de :

- sélectionner le canal, la région et la catégorie ;
- sélectionner une période ;
- afficher les KPI ;
- visualiser les ventes mensuelles ;
- visualiser l'évolution de la marge ;
- comparer les marges par canal ;
- consulter les anomalies ;
- afficher le JSON envoyé au LLM ;
- générer et modifier le texte ;
- contrôler les chiffres ;
- effectuer la validation humaine ;
- télécharger le rapport en PDF.

Les graphiques sont construits avec Plotly. Les PDF sont générés avec ReportLab via `src/pdf_report.py`.

## 8. Pipeline en ligne de commande

Le pipeline complet se trouve dans `src/pipeline.py`.

Commandes principales :

```powershell
python -m unittest discover -s tests -v
python -m src.pipeline --scenario S02
python -m src.pipeline --all
streamlit run app.py
```

Les résultats sont enregistrés dans le dossier `outputs/`.

## 9. Validation humaine

Chaque rapport est initialement marqué :

```text
AI DRAFT - not yet validated by a human
```

Le module `src/validate.py` demande au relecteur de vérifier :

1. l'exactitude des chiffres ;
2. l'absence de causes présentées comme des faits ;
3. la clarté du périmètre ;
4. l'adaptation du ton à un public dirigeant.

Le rapport devient ensuite `VALIDATED` ou `NEEDS REVISION`. La décision est enregistrée dans `outputs/validation_log.csv`.

## 10. Tests

Les tests de `tests/test_project.py` et `tests/test_pdf_report.py` vérifient notamment :

- les totaux Power BI ;
- la période couverte ;
- les règles de détection ;
- les années partielles ;
- les scénarios sans anomalie ;
- les filtres inconnus ;
- le contrôle des chiffres ;
- la sérialisation JSON ;
- la validation humaine ;
- la génération PDF.

## 11. Scénarios et évaluation

Le fichier `scenarios/scenarios.json` contient 20 scénarios :

- vue globale ;
- différents canaux, régions et catégories ;
- périodes spécifiques ;
- périmètres sans anomalie ;
- filtres sans données.

Les sorties d'exemple sont disponibles dans `outputs/examples/`.

Le fichier `scenarios/ground_truth.csv` sert de matrice d'évaluation. Il doit être rempli avec les réponses d'un vrai LLM afin de mesurer :

- l'exactitude des chiffres ;
- la couverture des anomalies ;
- l'absence de causes inventées ;
- la qualité du ton.

## 12. Limites techniques et métier

- Les données sont statiques et ne sont pas connectées directement à Power BI.
- Il n'existe pas de données d'objectifs ou de cibles.
- Les années 2017 et 2020 sont partielles.
- Les seuils de détection sont des valeurs initiales à calibrer.
- Les segments contributeurs ne représentent pas nécessairement les causes commerciales.
- Le contrôle numérique ne garantit pas l'absence totale d'hallucination.
- Le mode `mock` ne permet pas d'évaluer un véritable LLM.
- Une validation humaine reste nécessaire avant diffusion du rapport.

## Conclusion

Le projet est une solution de **Generative BI contrôlée**. Il associe une analyse Python reproductible, une génération de texte par IA, des contrôles contre les chiffres inventés, une interface interactive, un export de rapport et une validation humaine. Sa caractéristique technique principale est la séparation entre le calcul déterministe réalisé par le code et la rédaction effectuée par le LLM.
