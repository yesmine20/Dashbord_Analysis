# Sujet 15 - Résumé exécutif et explication des anomalies (Generative BI)

À partir des KPI d'un rapport Power BI (**AdventureWorks Sales**), le projet produit un résumé exécutif et explique les
anomalies détectées, avec une **étape de validation humaine**.

Principe : **le code calcule, le LLM raconte, l'humain valide.**

1. `src/detect.py` calcule les KPI et détecte les anomalies (règles déterministes, sans LLM) et produit un JSON.
2. Le LLM reçoit **uniquement** ce JSON et rédige le texte. Il ne calcule rien et ne donne que des « facteurs possibles ».
3. `src/check_numbers.py` vérifie que chaque chiffre du texte existe dans le JSON.
4. Un humain relit et valide (`src/validate.py` ou l'application Streamlit).

## Contenu

```
app.py                       application Streamlit (KPI, graphiques, texte IA, validation, export Markdown)
data/export_kpi_mensuel.csv  export du rapport Power BI (461 lignes, 2017-07 à 2020-06)
src/                         load_data, detect, prompts, llm_client, mock_llm, check_numbers, report, validate, pipeline
scenarios/scenarios.json     20 scénarios (dont 2 sans anomalie et 3 hors données)
scenarios/ground_truth.csv   matrice de recette (vraies valeurs + colonnes à remplir)
outputs/examples/            résultats de démonstration des 20 scénarios (générés en mode "mock")
tests/                       14 tests automatiques
docs/                        architecture, règles de détection, modèle de note pédagogique, répartition A/B, inventaire des visuels Power BI
```

## Installation (Windows, PowerShell)

```powershell
cd sujet15_exec_summary
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
Python 3.10 ou plus récent est nécessaire.

## Démarrage rapide (sans clé API)

```powershell
python -m unittest discover -s tests -v          # 14 tests
python -m src.pipeline --scenario S02            # un scénario -> outputs/S02_input.json et S02_report.md
python -m src.pipeline --all                     # les 20 scénarios
python -m src.pipeline --channel Reseller --start 2018-01 --end 2018-12
streamlit run app.py                             # interface
```

Par défaut le fournisseur est `mock` : ce n'est **pas** un modèle de langage, mais un gabarit qui recopie les chiffres du
JSON. Il permet de tester toute la chaîne sans clé. Pour juger la qualité réelle des textes, utilisez un vrai LLM.

## Utiliser un vrai LLM

1. Créez ou modifiez le fichier `.env` à la racine du projet.
2. Renseignez `LLM_PROVIDER` (`openai`, `azure`, `anthropic` ou `groq`), `LLM_MODEL` (nom du modèle, ou du déploiement pour Azure)
   et la clé correspondante. Pour Groq, créez une clé sur [console.groq.com/keys](https://console.groq.com/keys), renseignez `GROQ_API_KEY`,
   puis choisissez un identifiant de modèle actuellement disponible dans votre compte Groq.
3. Lancez `python -m src.pipeline --scenario S01 --provider groq`, ou `streamlit run app.py` puis choisissez `groq` dans la liste.

Le paramètre `--provider groq` force Groq pour cette exécution. Sans paramètre explicite, le pipeline utilise `LLM_PROVIDER` du fichier `.env`.
L'application sélectionne aussi ce fournisseur par défaut. La réponse « aucune anomalie à expliquer » est déterministe et ne passe pas par un LLM.

Exemple de configuration Groq dans `.env` :

```dotenv
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-120b
GROQ_API_KEY=colle_ta_cle_ici
```

Le nom du modèle proposé est un exemple : vérifie dans la console Groq les modèles disponibles pour ta clé. Ne partage jamais
ta clé et ne la colle pas dans le code ou dans un fichier suivi par Git.

Les prompts sont dans `src/prompts.py` (en anglais, comme demandé). Le prompt système impose : n'utiliser que le JSON,
recopier les chiffres « display », répondre `No data available` sinon, ne jamais présenter une cause comme un fait.

## Règles de détection

| Règle | Détecte |
|---|---|
| R1 | mois à marge négative ou très inférieure à la base des 3 mois précédents |
| R2 | variation de ventes d'un mois à l'autre (≥ 15 % **et** ≥ 1 M$, hausses incluses) |
| R3 | 6 derniers mois vs mêmes 6 mois un an avant (comparaison « à périodes égales ») |
| R4 | écart de marge entre canaux (Internet / Reseller) |
| R5 | catégorie ou région dont la marge s'écarte fortement de celle du périmètre |

Détails et seuils : `docs/rules.md` et `src/config.py`.

## Scénarios et matrice de recette

- `python -m src.build_ground_truth` régénère `scenarios/ground_truth.csv` (séparateur `;`, s'ouvre directement dans Excel).
- Pour chaque scénario : lancez le LLM, collez la réponse, puis notez (0/1) l'exactitude des chiffres, les anomalies
  couvertes, l'absence de cause inventée et le ton.
- Les scénarios S12-S13 (aucune anomalie) testent les faux positifs. S15-S17 (région, année ou catégorie inexistantes)
  doivent répondre exactement `No data available`.
- Pour arriver à 20 scénarios « réels » comme dans le sujet, ajoutez-en dans `scenarios/scenarios.json` puis relancez
  la commande ci-dessus.

## Validation humaine

```powershell
python -m src.validate outputs/S02_report.md --reviewer "Votre nom"
```
Une checklist de 4 questions est posée. Le statut du rapport passe de `AI DRAFT` à `VALIDATED` ou `NEEDS REVISION`, et la
décision est ajoutée à `outputs/validation_log.csv`. L'application Streamlit propose la même checklist.

## Mettre à jour les données

Réexportez le visuel Tableau depuis Power BI (mêmes colonnes : Year, Month, Category, Group, Channel, Sales, Cost, Profit,
Profit %, Orders), remplacez `data/export_kpi_mensuel.csv`, puis mettez à jour `EXPECTED_TOTALS` dans `src/config.py`
avec la ligne « Total » du tableau. Le pipeline affiche `Data check vs Power BI totals: OK` quand les totaux concordent.

## Limites connues (à écrire dans la note pédagogique)

- **Pas d'objectifs** dans ce jeu de données : pas d'écart « réel vs cible ».
- **Années partielles** : 2017 (juillet-décembre) et 2020 (janvier-juin). Les comparaisons annuelles se font à périodes égales.
- **`Orders` n'est pas additif** entre lignes : exclu de l'analyse.
- **Seuils** choisis pour démarrer : à justifier ou ajuster. Les ventes mensuelles sont très irrégulières, d'où le double seuil.
- **« 0 % d'hallucination » ne se décrète pas** : le prompt et le contrôle des chiffres réduisent le risque, la validation
  humaine reste nécessaire. Le contrôle vérifie les chiffres, pas la justesse de l'interprétation.
- **Vérification à effectuer** : Streamlit et les fournisseurs LLM réels n'ont pas été exécutés ici. Le dépôt contient 14 tests automatisés; leur exécution nécessite Python 3.10+ et les dépendances installées.

Dans l'application, le bouton **Download report (PDF)** télécharge le rapport au format PDF. Après **Record decision**, une copie du rapport validé est également enregistrée dans `outputs/` et le journal de validation référence ce fichier PDF.


## État du livrable pédagogique

La note finalisée est dans `docs/note_pedagogique.md`. Les exemples sous `outputs/examples/` sont générés en mode `mock` (hors ligne) et illustrent le parcours; ils ne mesurent pas la qualité d'un LLM. La matrice `scenarios/ground_truth.csv` reste à renseigner avec les réponses d'un vrai modèle avant de conclure sur l'exactitude et le ton.

