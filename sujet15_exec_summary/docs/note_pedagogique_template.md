# Note pédagogique (à compléter)

## 1. Objectif et périmètre
(Générer un résumé exécutif et expliquer les anomalies d'un dashboard Power BI. Dashboard : AdventureWorks Sales.)

## 2. Données et préparation
- Source : export Power BI (visuel Tableau, données résumées), 461 lignes, 2017-07 à 2020-06.
- Contrôle : totaux du CSV = totaux du rapport (voir `reconcile` dans src/load_data.py).
- Limites : pas d'objectifs; années 2017 et 2020 partielles; `Orders` non additif.

## 3. Approche de détection
(Décrire les 5 règles et les seuils : voir docs/rules.md. Justifier seuil relatif + absolu.)

## 4. Stratégie de prompting et garde-fous
(Prompt système, 3 paragraphes pour le résumé, « facteurs contributeurs » pour les anomalies, "No data available".)

## 5. Validation humaine
(Checklist, statut « AI DRAFT » → « VALIDATED », journal validation_log.csv.)

## 6. Résultats sur la matrice de recette
(Tableau issu de scenarios/ground_truth.csv rempli : exactitude des chiffres, anomalies couvertes, causes inventées,
ton. Inclure les scénarios sans anomalie et hors données.)

## 7. Limites et pistes
(0 % d'hallucination non garanti; comparaison avec Copilot de Power BI; objectifs absents; seuils à calibrer.)
