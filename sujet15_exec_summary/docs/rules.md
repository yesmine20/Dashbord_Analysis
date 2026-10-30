# Règles de détection (src/detect.py) et seuils (src/config.py)

| Règle | Détecte | Condition par défaut | Classement |
|---|---|---|---|
| R1 margin_alert | mois à marge négative ou très inférieure à la base des 3 mois précédents | ventes du mois ≥ 100 K$ et (profit < 0 ou baisse ≥ 5 pts) | impact en profit |
| R2 sales_variation | variation de ventes d'un mois à l'autre | variation ≥ 15 % **et** ≥ 1 M$ (hausses incluses) | variation en $ |
| R3 like_for_like_yoy | 6 derniers mois vs mêmes 6 mois un an avant | variation ≥ 15 % **et** ≥ 1 M$ | - |
| R4 channel_gap | écart de marge entre canaux (Internet / Reseller) | écart ≥ 20 pts | - |
| R5 segment_outlier | catégorie ou région dont la marge s'écarte de celle du périmètre | écart ≥ 10 pts et ventes ≥ 1 M$ | impact en profit |

- Au maximum 5 anomalies par règle sont transmises au LLM. Le JSON indique combien ont été détectées au total
  (`meta.rule_counts`) et une limite le précise.
- Chaque anomalie R1-R3 contient des **contributeurs** (segments qui expliquent le mouvement : canal, catégorie, région).
  Ce sont des facteurs contributeurs, pas des causes.
- Pourquoi un seuil relatif ET absolu : sur ce jeu de données les ventes mensuelles sont très irrégulières (commandes de
  revendeurs), un seuil de 15 % seul signalerait presque tous les mois.

## À discuter avec l'encadrant / l'équipe
- Les seuils sont des choix de départ, à justifier ou ajuster dans `src/config.py`.
- Le jeu de données n'a pas d'objectifs : l'écart « réel vs cible » n'est pas calculable ici.
