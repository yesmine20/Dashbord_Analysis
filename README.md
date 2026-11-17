# Sujet 15 — Executive Summary & Anomalies

Projet de **Generative BI** construit autour du modèle sémantique Power BI
**AdventureWorks Sales**. L'application transforme des mesures Power BI en
indicateurs, détecte les anomalies avec des règles déterministes, demande à un
LLM de rédiger un résumé et impose une validation humaine avant diffusion.

> **Principe : le code calcule, le LLM raconte, l'humain valide.**

## 1. Objectifs

Le projet répond aux besoins suivants :

- exploiter les mesures et relations du modèle Power BI comme source de vérité ;
- filtrer l'analyse par canal, groupe géographique, catégorie et période ;
- calculer les KPI Sales, Cost, Profit et marge ;
- détecter automatiquement les variations et écarts significatifs ;
- transmettre au LLM uniquement un JSON analytique contrôlé ;
- vérifier les nombres présents dans le texte généré ;
- produire un rapport Markdown ou PDF ;
- faire valider le rapport par un relecteur humain ;
- conserver les scénarios, sorties et résultats de recette.

Le projet n'essaie pas de déterminer une cause commerciale certaine. Il indique
où et quand une variation est observée, puis présente les segments contributeurs
comme des **facteurs possibles**.

## 2. Fonctionnement global

```text
PBIP / modèle Power BI
        |
        v
Catalogue TMDL + requête DAX
        |
        v
Résultats mensuels par segment
        |
        v
Filtres et KPI
        |
        v
Détection déterministe des anomalies
        |
        v
Payload JSON contrôlé
        |
        v
Résumé et explication par LLM
        |
        v
Contrôle des nombres
        |
        v
Rapport Markdown / PDF
        |
        v
Validation humaine et journal d'audit
```

Le LLM ne reçoit pas directement le fichier PBIP ni le CSV. Il reçoit seulement
le payload construit par `src/detect.py`.

## 3. Structure du dépôt

```text
app.py                              Interface Streamlit
requirements.txt                    Dépendances Python
AdventureWorks Sales.pbip           Projet Power BI Desktop (PBIP)
AdventureWorks Sales.Report/        Définition du rapport et des visuels
AdventureWorks Sales.SemanticModel/ Modèle sémantique TMDL et relations

src/
  config.py                         Chemins, mesures, devise et seuils
  semantic_model.py                 Catalogue et validation PBIP/TMDL
  powerbi.py                        Requête DAX, ADOMD.NET et API REST
  load_data.py                      Chargement, normalisation et filtres
  detect.py                         KPI et détection déterministe
  prompts.py                        Prompts système et prompts de tâches
  llm_client.py                     Adaptateurs Groq
  check_numbers.py                  Contrôle des chiffres générés
  report.py                         Génération du rapport Markdown
  pdf_report.py                     Conversion Markdown vers PDF
  validate.py                       Checklist et journal de validation
  pipeline.py                       Exécution en ligne de commande

data/                               Données/export de référence
scenarios/                          Scénarios et matrice de recette
outputs/                            Rapports et payloads générés
tests/                              Tests automatisés
docs/                               Documentation technique et pédagogique
```

Les dossiers `.pbi/` sont des fichiers locaux générés par Power BI Desktop
(cache, paramètres de session, requêtes de l'éditeur) et sont ignorés par Git.

## 4. Installation sous Windows

Depuis le dossier contenant `app.py` :

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Python **3.10 ou plus récent** est requis.

Les dépendances principales sont :

- `pandas` et `numpy` pour la préparation et l'analyse ;
- `streamlit` pour l'interface ;
- `plotly` pour les graphiques ;
- `reportlab` pour les PDF ;
- `pythonnet` sous Windows pour ADOMD.NET ;
- ` Groq ;
- `anthropic` pour Anthropic.

## 5. Configuration des données Power BI

### 5.1 Modèle local Power BI Desktop

1. Ouvrir `AdventureWorks Sales.pbip` avec Power BI Desktop.
2. Garder le modèle ouvert et chargé.
3. Récupérer le serveur local et le catalogue de la session Power BI.
4. Ajouter ces variables dans un fichier `.env` à la racine :

```dotenv
POWERBI_EXECUTION_MODE=local
POWERBI_ADOMD_DATA_SOURCE=<serveur-local-power-bi>
POWERBI_ADOMD_CATALOG=<catalogue-local-power-bi>
POWERBI_ADOMD_DLL=<chemin-optionnel-vers-Microsoft.AnalysisServices.AdomdClient.dll>
```

Le port et l'identifiant du catalogue peuvent changer à chaque session Power BI.
Ne remplacez pas un `.env` existant : il peut déjà contenir des clés LLM.

Sous Windows, `pythonnet` charge l'assembly ADOMD.NET. Si elle n'est pas
accessible dans le chemin .NET, renseigner explicitement `POWERBI_ADOMD_DLL`.

### 5.2 Power BI Service / Fabric

Le module `src/powerbi.py` peut aussi utiliser l'endpoint REST
`executeQueries` :

```dotenv
POWERBI_EXECUTION_MODE=cloud
POWERBI_TENANT_ID=<tenant-id>
POWERBI_CLIENT_ID=<application-id>
POWERBI_CLIENT_SECRET=<secret>
POWERBI_DATASET_ID=<dataset-id>
```

Le principal de service doit avoir les droits Azure/Power BI nécessaires.
Les secrets ne doivent jamais être commités, copiés dans le README ou ajoutés
à un fichier suivi par Git.

### 5.3 Contrat DAX et modèle TMDL

La requête standard regroupe les mesures par :

- `'Date'[Month]` ;
- `Product[Category]` ;
- `'Sales Territory'[Group]` ;
- `'Sales Order'[Channel]`.

Elle renvoie les mesures `[Sales]`, `[Cost]`, `[Profit]` et `[Orders]`.
`src/semantic_model.py` lit les fichiers TMDL, catalogue les tables, colonnes,
mesures et relations, puis permet de vérifier que la requête correspond au
modèle.

La date utilisée est la relation active :
`Sales[OrderDateKey] -> Date[DateKey]`.

## 6. Configuration d'un fournisseur LLM

Le fournisseur est choisi avec `LLM_PROVIDER`. Les adaptateurs disponibles dans
`src/llm_client.py` sont  `groq`.

### Groq

```dotenv
LLM_PROVIDER=groq
LLM_MODEL=<modele-disponible-dans-le-compte>
GROQ_API_KEY=<cle>
```

Le fournisseur par défaut est lu dans `LLM_PROVIDER`. Si aucune variable n'est
définie, le code utilise la valeur `mock` par défaut, mais le fournisseur mock
doit être implémenté/configuré avant une exécution complète de génération.
Pour une démonstration reproductible sans API, utiliser les sorties déjà
présentes dans `outputs/examples/` ou ajouter un adaptateur mock.

## 7. Lancer l'application Streamlit

```powershell
streamlit run app.py
```

L'interface permet de :

1. charger les données du modèle Power BI ;
2. choisir le périmètre d'analyse ;
3. afficher les KPI et les graphiques Plotly ;
4. consulter les anomalies et le JSON transmis au LLM ;
5. générer le résumé exécutif et l'explication ;
6. vérifier les nombres ;
7. télécharger le rapport PDF ;
8. enregistrer la décision humaine.

Si la connexion Power BI échoue, l'application affiche l'erreur technique et
les variables d'environnement nécessaires au lieu de produire un rapport avec
des données silencieusement incomplètes.

## 8. Lancer le pipeline CLI

```powershell
# Scénario précis
python -m src.pipeline --scenario S02

# Tous les scénarios
python -m src.pipeline --all

# Périmètre personnalisé
python -m src.pipeline --channel Reseller --start 2018-01 --end 2018-12

# Fournisseur explicite
python -m src.pipeline --scenario S02 --provider groq

# Dossier de sortie personnalisé
python -m src.pipeline --scenario S02 --out-dir outputs/test
```

Pour chaque exécution, le pipeline :

1. charge le modèle sémantique ;
2. exécute la requête DAX ;
3. sélectionne les scénarios ou filtres demandés ;
4. construit le payload d'analyse ;
5. génère le résumé et l'explication ;
6. vérifie les chiffres ;
7. écrit `<nom>_input.json` et `<nom>_report.md`.

## 9. Règles de détection

Les règles sont exécutées sans LLM dans `src/detect.py`. Les seuils sont
centralisés dans `src/config.py` et documentés dans `docs/rules.md`.

| Règle | Fonction |
|---|---|
| R1 | Alerte de marge négative ou nettement inférieure à la base des 3 mois précédents |
| R2 | Variation mensuelle des ventes au-dessus de 15 % et de 1 M$ |
| R3 | Comparaison des 6 derniers mois avec les mêmes 6 mois de l'année précédente |
| R4 | Écart de marge d'au moins 20 points entre les canaux |
| R5 | Catégorie ou groupe dont la marge s'écarte d'au moins 10 points de la marge globale |

Précisions importantes :

- R1 ignore les mois dont les ventes sont inférieures à 100 000 $ ;
- R5 exige au moins 1 M$ de ventes pour un segment ;
- seules les anomalies les plus importantes par règle sont rapportées ;
- un score Z est calculé lorsqu'une base historique et un écart-type utilisable
  sont disponibles ;
- `Orders` est conservé comme mesure de référence, mais n'est pas additionné
  dans l'analyse car un décompte de commandes n'est pas additif entre lignes.

## 10. Payload et génération du texte

`build_payload()` retourne un objet JSON avec notamment :

- `status` : `ok` ou `no_data` ;
- `meta` : périmètre, période, devise, seuils et compteurs ;
- `kpis` : ventes, coût, profit et marge ;
- `breakdown` : répartition par canal, catégorie et groupe ;
- `yearly` : comparaison annuelle et nombre de mois disponibles ;
- `anomalies` : anomalies détectées et contributeurs ;
- `limitations` : limites à rappeler dans le rapport.

Les prompts dans `src/prompts.py` demandent au LLM :

- de n'utiliser que le JSON fourni ;
- de recopier les nombres affichés ;
- de ne pas présenter une cause comme un fait ;
- de distinguer observations et facteurs possibles ;
- de répondre `No data available` si le périmètre ne contient aucune donnée.

## 11. Contrôle anti-hallucination

`src/check_numbers.py` extrait les nombres du texte produit et vérifie leur
présence dans le payload JSON. Le contrôle détecte notamment :

- un montant inventé ;
- un pourcentage absent des données ;
- une valeur modifiée ou arrondie de manière inattendue.

Ce garde-fou ne prouve pas que le texte est parfaitement pertinent : il vérifie
les chiffres, pas toute la logique métier ni toutes les formulations.

## 12. Validation humaine et exports

Pour valider un rapport généré :

```powershell
python -m src.validate outputs/S02_report.md --reviewer "Votre nom"
```

La checklist vérifie :

1. l'exactitude des chiffres ;
2. l'absence de causes présentées comme des faits ;
3. la clarté du périmètre ;
4. l'adaptation à un public dirigeant.

La décision devient `VALIDATED` ou `NEEDS REVISION`. Elle est ajoutée à
`outputs/validation_log.csv`. L'application Streamlit propose le même parcours
et permet de télécharger le rapport au format PDF.

## 13. Scénarios et recette

`scenarios/scenarios.json` contient les périmètres de test. La matrice
`scenarios/ground_truth.csv` peut être régénérée avec :

```powershell
python -m src.build_ground_truth
```

Les scénarios couvrent notamment :

- la vue globale ;
- les canaux, régions et catégories ;
- des périodes spécifiques ;
- des périmètres sans anomalie ;
- des filtres inconnus ou sans données.

Les fichiers `outputs/examples/` sont des exemples de rapports. Avant de
conclure sur la qualité d'un LLM, il faut compléter la matrice avec des réponses
réelles et évaluer les chiffres, la couverture des anomalies, l'absence de
causes inventées et le ton.

## 14. Tests

Commande principale :

```powershell
python -m unittest discover -s tests -v
```

Les tests couvrent notamment :

- la structure du projet ;
- le catalogue TMDL et les contrats DAX ;
- la génération de requêtes et le push-down des filtres ;
- la normalisation des résultats Power BI ;
- les règles statistiques et anomalies ;
- les filtres et scénarios sans données ;
- le contrôle des nombres ;
- la génération PDF ;
- la validation du rapport.

Les tests qui interrogent Power BI en direct nécessitent une instance Power BI
Desktop ou une configuration cloud valide. Ils doivent être traités comme des
tests d'intégration et non comme de simples tests unitaires.

## 15. Documentation complémentaire

- `docs/RESUME_TECHNIQUE.md` : architecture et fonctionnement détaillé ;
- `docs/PLAN_ET_EXECUTION.md` : feuille de route et guide d'exécution ;
- `docs/architecture.md` : architecture fonctionnelle ;
- `docs/rules.md` : règles et seuils d'anomalie ;
- `docs/note_pedagogique.md` : note destinée à la présentation pédagogique ;
- `docs/plan-migration-powerbi-service.md` : préparation d'un déploiement Power BI Service ;
- `AdventureWorks Sales.SemanticModel/definition/` : tables, mesures et relations TMDL.

## 16. Limites connues

- Les données viennent des mesures du modèle et dépendent de la disponibilité de
  Power BI Desktop ou de Power BI Service.
- Les années peuvent être partielles ; les comparaisons utilisent des fenêtres
  comparables lorsque c'est possible.
- Le modèle ne contient pas de cibles commerciales : aucun écart réel-versus-cible
  n'est calculé.
- Les seuils sont des paramètres de départ et doivent être calibrés avec le
  métier.
- Les segments contributeurs indiquent une corrélation descriptive, pas une
  causalité.
- Le contrôle numérique ne garantit pas l'absence totale d'hallucination.
- Une validation humaine reste obligatoire avant diffusion.
