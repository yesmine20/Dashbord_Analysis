# Note pédagogique — Projet 15 : résumé exécutif et anomalies d’un dashboard

## 1. Objectif et scénario métier

Un responsable consulte un tableau de bord Power BI et veut comprendre rapidement les performances, les changements importants et les points qui méritent une vérification. Le projet transforme un export mensuel de KPI en un résumé court et en commentaires sur les anomalies. Le texte produit par l’IA reste un brouillon : une personne le relit et décide s’il peut être partagé.

**Principe de conception : le code calcule, le modèle rédige, une personne valide.** Le modèle ne reçoit pas les lignes détaillées du fichier source : il reçoit un JSON agrégé préparé par le moteur d’analyse.

## 2. Données et nettoyage

La démonstration utilise un export du rapport Power BI AdventureWorks Sales. Le CSV contient 461 lignes, avec des champs de période, catégorie, région (`Group`), canal, ventes, coût, profit et commandes. La période couverte est juillet 2017 à juin 2020. La devise retenue est le dollar américain et le sélecteur de date de l’export est « Order Date ».

Le module `src/load_data.py` effectue la préparation reproductible : lecture UTF‑8 avec BOM, normalisation des en-têtes, conversion des montants texte en nombres, conversion du mois en date mensuelle, nettoyage des libellés et exclusion des lignes sans date ou mesure financière exploitable. Les colonnes conservées et leur ordre sont explicités dans le code. `src/config.py` définit les totaux de référence issus du rapport; `reconcile` compare les totaux du fichier à ces références avec une tolérance de 0,01 %.

Cette préparation est utile pour l’analyse, mais elle ne remplace pas une validation de qualité complète. Avant une présentation, vérifier le nombre de lignes rejetées, les doublons métier, la cohérence Year/Month, les valeurs manquantes dans les dimensions et la règle de calcul du profit dans le modèle Power BI. Le chargement actuel supprime les lignes incomplètes sans produire de bilan détaillé de ces rejets. `Orders` est conservé à la source mais exclu des agrégations, car cette mesure n’est pas additive entre lignes.

## 3. Méthode d’analyse et détection

`src/detect.py` applique cinq règles déterministes configurées dans `src/config.py`. Les seuils sont des paramètres de démonstration à justifier avec un responsable métier et à calibrer sur des périodes représentatives.

- **R1 — marge mensuelle :** signale un profit négatif ou une marge d’au moins 5 points sous la marge pondérée des trois mois précédents. Les mois sous 100 000 $ de ventes sont écartés.
- **R2 — variation mensuelle des ventes :** signale une hausse ou une baisse d’au moins 15 % et 1 000 000 $ par rapport au mois précédent. Les deux conditions réduisent les alertes déclenchées par de petits montants.
- **R3 — comparaison annuelle à période comparable :** compare les six derniers mois consécutifs aux mêmes six mois de l’année précédente, avec les seuils de R2.
- **R4 — écart entre canaux :** signale un écart d’au moins 20 points de marge entre les canaux présents dans le périmètre.
- **R5 — écart de segment :** signale une catégorie ou région avec un écart de marge d’au moins 10 points par rapport au périmètre et au moins 1 000 000 $ de ventes.

Le moteur classe les alertes par impact et transmet au plus cinq alertes par règle. Le JSON indique aussi les nombres détectés et rapportés. Les contributeurs sont des segments associés à une variation; ils n’établissent pas la cause de cette variation.

## 4. Génération du texte et garde-fous

Le pipeline suit le schéma `CSV → préparation → KPI et règles → JSON → génération → contrôle des chiffres → brouillon Markdown → validation humaine`. Le schéma détaillé se trouve dans `docs/architecture.md`.

Le mode `mock`, utilisé par défaut, produit des textes à partir de gabarits hors ligne. Il permet une démonstration reproductible sans clé API, mais **ce n’est pas une IA générative et il ne démontre pas la qualité d’un LLM**. Pour montrer réellement la partie « IA générative », configurer un fournisseur pris en charge dans `.env`, ne jamais versionner la clé, puis exécuter au moins quelques scénarios représentatifs avec le modèle choisi.

Le prompt système impose au modèle de s’appuyer uniquement sur le JSON, de conserver les valeurs affichées, d’indiquer le périmètre, de ne pas inventer de causes et de répondre « No data available » en l’absence de données. Les causes restent formulées comme des facteurs possibles. Le contrôle dans `src/check_numbers.py` vérifie que les nombres repérés dans le texte figurent dans le JSON. Ce contrôle ne vérifie ni le sens des phrases, ni la bonne attribution d’un chiffre, ni l’exhaustivité des anomalies; la validation humaine reste indispensable.

## 5. Validation humaine

Chaque rapport est marqué **AI DRAFT** jusqu’à sa relecture. La checklist demande de confirmer les chiffres, d’éviter les causes présentées comme des faits, de rendre le périmètre compréhensible et d’adopter un ton adapté à une direction. Le relecteur peut valider ou demander une révision; la décision et les notes sont consignées dans `outputs/validation_log.csv`. L’application Streamlit permet également de corriger le texte avant de consigner la décision.

Pour la démonstration en classe : choisir un scénario, afficher les KPI et les anomalies détectées, générer le texte, ouvrir le JSON transmis, modifier si nécessaire le texte puis compléter la checklist et exporter le rapport Markdown.

## 6. Scénarios et évaluation

`scenarios/scenarios.json` contient 20 périmètres : vue globale, canaux, régions, catégories, période complexe, cas sans anomalie et filtres sans données. Les fichiers `outputs/examples/` montrent les sorties produites hors ligne en mode `mock`; ils illustrent le format et le parcours de bout en bout.

`scenarios/ground_truth.csv` est une matrice de recette à compléter avec les réponses du modèle réellement testé. Ses colonnes de notation couvrent l’exactitude des chiffres, la couverture des anomalies, l’absence de cause inventée et le ton. **Les cellules d’évaluation sont actuellement vides : aucun score de qualité d’un LLM ne peut donc être revendiqué à ce stade.** Les sorties `mock` ne doivent pas être présentées comme une évaluation de modèle.

Protocole conseillé : tester les 20 scénarios avec le même modèle et le même prompt; noter chaque critère (0 ou 1) avec une justification; faire relire les textes par une personne différente de celle qui a réglé le prompt; calculer les taux par critère et examiner séparément S12–S13 (faux positifs) et S15–S17 (absence de données). Archiver le nom/version du modèle, la date, le prompt et les réponses pour rendre la comparaison reproductible.

## 7. Difficultés, limites et bonnes pratiques

- Le jeu de données n’inclut pas d’objectifs : aucune analyse « réel contre cible » n’est possible.
- Les années 2017 et 2020 sont partielles; la comparaison annuelle doit utiliser des fenêtres identiques.
- Les ventes mensuelles sont irrégulières; les seuils combinés sont des choix initiaux et peuvent produire des alertes manquées ou excessives.
- Une variation et les segments qui y contribuent ne prouvent pas une explication commerciale. Il faut confronter toute hypothèse aux commandes et au contexte métier.
- Le contrôle numérique diminue le risque de chiffres non étayés, mais ne garantit pas l’absence d’hallucination.
- La solution est une démonstration locale basée sur un export statique; elle n’est pas connectée en direct à Power BI et ne gère pas les mises à jour automatiques du rapport.
- La clé API, les données sensibles et les sorties contenant des informations confidentielles doivent être gérées selon les règles de l’organisation.

## 8. Répartition possible pour trois élèves

1. **Données et Power BI :** documenter l’export, vérifier le nettoyage et les totaux, confirmer les définitions métier des mesures.
2. **Analyse et détection :** expliquer les règles, justifier les seuils et préparer les scénarios de recette.
3. **IA, application et restitution :** configurer le modèle, examiner les prompts et garde-fous, conduire la validation humaine et présenter les limites.

Les trois élèves relisent ensemble la démonstration finale. La personne qui valide les réponses ne devrait pas être celle qui a rédigé le prompt seul.

## 9. Conclusion

Le projet est aligné avec la mission du Projet 15 : il transforme des KPI issus d’un rapport Power BI en résumé, détecte des évolutions par des règles reproductibles, propose un texte explicatif encadré et prévoit une décision humaine. Pour revendiquer une démonstration d’IA générative complète, il reste à exécuter le pipeline avec un vrai fournisseur LLM et à renseigner la matrice de recette à partir de ces réponses. Le mode hors ligne sert à prouver la reproductibilité technique et le parcours de validation, pas la performance d’un modèle.
