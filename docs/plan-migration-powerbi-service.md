# Plan de migration de Power BI Desktop local vers Power BI Service/Fabric

## 1. Objectif

Le projet fonctionne actuellement avec une dépendance directe à Power BI Desktop :

```text
Application Streamlit
        ↓
Connexion ADOMD.NET
        ↓
Power BI Desktop ouvert localement
        ↓
Modèle sémantique local
        ↓
Résultat DAX
```

Cette architecture est adaptée au développement et à la démonstration, mais elle n'est pas adaptée à une application d'entreprise. L'objectif est de conserver Power BI Desktop pour le développement et de déplacer l'exécution vers Power BI Service ou Microsoft Fabric.

Architecture cible :

```text
Power BI Desktop
        ↓ publication
Power BI Service / Microsoft Fabric
        ↓ dataset publié
Power BI REST API ou XMLA Endpoint
        ↓
Application Streamlit ou service Python
        ↓
Analyse, détection et rapport
```

Power BI Desktop ne devra plus être ouvert pour exécuter l'application.

---

## 2. Situation actuelle du projet

La dépendance locale est principalement portée par [`src/powerbi.py`](../src/powerbi.py).

Le fichier utilise :

- `POWERBI_ADOMD_DATA_SOURCE` : généralement un serveur local `localhost:xxxxx` ;
- `POWERBI_ADOMD_CATALOG` : catalogue du modèle local ;
- `POWERBI_ADOMD_DLL` : bibliothèque ADOMD.NET installée sur le poste ;
- un Power BI Desktop ouvert avec le fichier PBIP.

La requête DAX principale est :

```DAX
EVALUATE
SUMMARIZECOLUMNS(
    'Date'[Month],
    Product[Category],
    'Sales Territory'[Group],
    'Sales Order'[Channel],
    "Sales", [Sales],
    "Cost", [Cost],
    "Profit", [Profit],
    "Orders", [Orders]
)
ORDER BY
    'Date'[Month],
    Product[Category],
    'Sales Territory'[Group],
    'Sales Order'[Channel]
```

Le projet reçoit les données DAX dans [`src/load_data.py`](../src/load_data.py), puis les filtres sont appliqués localement avec pandas. Les règles d'anomalies sont exécutées dans [`src/detect.py`](../src/detect.py).

---

## 3. Choix de la solution cible

### 3.1 Power BI REST API `executeQueries`

Cette solution est recommandée pour la première migration.

Flux :

```text
Python
  ↓ HTTPS + token Entra ID
Power BI REST API
  ↓
Dataset publié
  ↓
Résultat DAX JSON
```

Avantages :

- intégration Python relativement simple ;
- aucun Power BI Desktop requis ;
- aucune DLL ADOMD.NET locale ;
- déploiement possible sur un serveur ou dans le cloud ;
- adaptée à l'application actuelle.

Limites :

- limites de volume et de fréquence des requêtes ;
- dépendance aux droits Power BI ;
- moins adaptée aux traitements massifs ;
- nécessite une configuration correcte du tenant.

### 3.2 XMLA Endpoint

XMLA est une solution plus orientée entreprise, notamment pour les capacités Power BI Premium ou Fabric.

Flux :

```text
Python
  ↓ connexion XMLA authentifiée
Power BI Premium / Fabric
  ↓
Modèle sémantique
```

Avantages :

- connexion plus proche du moteur Analysis Services ;
- meilleure adaptation aux modèles importants ;
- possibilités avancées d'administration et d'analyse.

Limites :

- configuration plus complexe ;
- coût de capacité Premium/Fabric ;
- bibliothèque cliente Analysis Services toujours nécessaire.

### 3.3 Recommandation

Pour ce projet :

1. commencer avec `executeQueries` ;
2. séparer les environnements Dev/Test/Prod ;
3. ajouter l'authentification Entra ID ;
4. passer à XMLA uniquement si le volume ou les exigences augmentent.

---

## 4. Préparer le modèle Power BI

Le modèle est situé dans :

[`AdventureWorks Sales.SemanticModel/`](../AdventureWorks%20Sales.SemanticModel)

Les éléments utilisés par Python doivent rester stables :

### Mesures

```text
Sales
Cost
Profit
Orders
```

### Dimensions

```text
Date[Month]
Product[Category]
Sales Territory[Group]
Sales Order[Channel]
```

### Vérifications à réaliser

- vérifier les relations du modèle ;
- vérifier les mesures DAX ;
- vérifier les types de données ;
- vérifier la date active `Sales[OrderDateKey] -> Date[DateKey]` ;
- vérifier les résultats dans Power BI Desktop ;
- vérifier le refresh du modèle ;
- vérifier qu'aucune mesure utilisée par Python n'est supprimée.

---

## 5. Corriger la source Excel absolue

Les partitions TMDL contiennent actuellement un chemin local absolu appartenant à une autre machine, par exemple :

```text
C:\Users\jterh\OneDrive - Microsoft\...\AdventureWorks Sales.xlsx
```

Ce chemin ne fonctionnera pas sur un serveur ou dans Power BI Service.

### Solutions possibles

Remplacer la source par :

- Azure SQL ;
- SQL Server avec gateway ;
- Azure Data Lake ;
- OneLake ;
- Fabric Lakehouse ;
- SharePoint contrôlé ;
- Dataflow Gen2 ;
- autre source centralisée.

### Solution temporaire : paramètre Power Query

Créer un paramètre :

```text
pSalesFilePath
```

Puis utiliser des valeurs différentes :

```text
Développement : C:\Data\AdventureWorks.xlsx
Production    : \\serveur\data\AdventureWorks.xlsx
```

Cette solution est préférable à un chemin codé en dur, mais une source centralisée reste recommandée pour la production.

---

## 6. Publier le modèle dans Power BI Service

### 6.1 Créer les workspaces

Créer au minimum :

```text
BI-Dev
BI-Test
BI-Prod
```

Le développement, les tests et la production doivent être séparés.

### 6.2 Publier le PBIP

Depuis Power BI Desktop :

1. ouvrir [`AdventureWorks Sales.pbip`](../AdventureWorks%20Sales.pbip) ;
2. vérifier que le modèle s'ouvre ;
3. vérifier le refresh ;
4. vérifier les mesures ;
5. publier dans `BI-Dev` ;
6. noter l'identifiant du workspace ;
7. noter l'identifiant du dataset ;
8. noter l'identifiant du rapport.

L'application Python ne devra plus utiliser le chemin du PBIP pour la production. Elle utilisera l'identifiant du dataset publié.

---

## 7. Créer une identité applicative

L'application ne doit pas utiliser le compte personnel d'un développeur.

### 7.1 App Registration

Dans Microsoft Entra ID :

1. créer une App Registration ;
2. noter le `Tenant ID` ;
3. noter le `Client ID` ;
4. créer un secret client ou un certificat ;
5. accorder uniquement les droits nécessaires.

Un certificat ou une identité managée est préférable à un secret statique.

### 7.2 Accès au workspace

Ajouter le service principal au workspace avec le niveau de droit minimal :

- Viewer pour une lecture simple ;
- Contributor seulement si nécessaire ;
- Admin uniquement pour les opérations d'administration.

Pour ce projet, l'accès en lecture seule devrait suffire.

### 7.3 Configuration du tenant

L'administrateur Power BI doit autoriser les service principals à utiliser les API Power BI, conformément à la politique de l'organisation.

Il faut également vérifier :

- les droits sur le workspace ;
- les droits sur le dataset ;
- les autorisations de requête ;
- le comportement de la sécurité RLS.

Si l'application doit respecter des droits différents selon l'utilisateur, il faut tester précisément l'identité utilisée. Une identité applicative unique peut ne pas suffire pour tous les scénarios RLS.

---

## 8. Nouvelle configuration

Pour le développement local uniquement, les variables peuvent être placées dans `.env` :

```dotenv
POWERBI_MODE=service
POWERBI_WORKSPACE_ID=workspace-id
POWERBI_DATASET_ID=dataset-id

AZURE_TENANT_ID=tenant-id
AZURE_CLIENT_ID=client-id
AZURE_CLIENT_SECRET=secret
```

En production, ne pas stocker ces secrets dans Git ou dans un fichier `.env` déployé.

Utiliser plutôt :

- Azure Key Vault ;
- variables secrètes CI/CD ;
- Managed Identity ;
- certificat ;
- secret manager de la plateforme d'hébergement.

---

## 9. Refactoriser les connecteurs Python

L'architecture actuelle doit être séparée en deux connecteurs.

### 9.1 Connecteur Desktop

Créer :

```text
src/connectors/powerbi_desktop.py
```

Responsabilités :

- connexion ADOMD.NET ;
- accès au modèle Power BI Desktop ;
- usage réservé au développement ;
- messages d'erreur locaux.

### 9.2 Connecteur Service

Créer :

```text
src/connectors/powerbi_service.py
```

Responsabilités :

- authentification Entra ID ;
- obtention du token ;
- appel de l'API Power BI ;
- récupération de la réponse JSON ;
- conversion en DataFrame ;
- gestion des erreurs HTTP.

### 9.3 Fabrique de connecteur

Créer :

```text
src/connectors/factory.py
```

Principe :

```python
if POWERBI_MODE == "desktop":
    return DesktopPowerBIConnector()
if POWERBI_MODE == "service":
    return ServicePowerBIConnector()
raise ValueError("Unsupported POWERBI_MODE")
```

Les deux connecteurs doivent exposer la même méthode :

```python
get_analysis_data() -> pd.DataFrame
```

Ainsi, [`src/load_data.py`](../src/load_data.py), [`src/detect.py`](../src/detect.py) et [`app.py`](../app.py) n'ont pas besoin de connaître le type de connexion.

Architecture :

```text
load_data.py
     ↓
PowerBI connector interface
     ├── Desktop connector
     └── Service connector
```

---

## 10. Appeler l'API Power BI

Le principe d'authentification est :

```python
from azure.identity import ClientSecretCredential

credential = ClientSecretCredential(
    tenant_id=tenant_id,
    client_id=client_id,
    client_secret=client_secret,
)

token = credential.get_token(
    "https://analysis.windows.net/powerbi/api/.default"
)
```

Le token est envoyé dans :

```http
Authorization: Bearer <token>
```

L'URL de requête utilise le dataset publié :

```text
https://api.powerbi.com/v1.0/myorg/datasets/{dataset_id}/executeQueries
```

Corps de la requête :

```json
{
  "queries": [
    {
      "Query": "EVALUATE SUMMARIZECOLUMNS(...)"
    }
  ],
  "serializerSettings": {
    "includeNulls": true
  }
}
```

La réponse doit être transformée depuis :

```text
results -> tables -> rows
```

vers un DataFrame pandas.

La normalisation actuelle de [`src/powerbi.py`](../src/powerbi.py) doit être conservée :

- simplification des noms de colonnes ;
- conversion des dates ;
- conversion des mesures numériques ;
- remplacement des valeurs nulles ;
- suppression des lignes invalides ;
- ajout de la colonne `Year`.

---

## 11. Améliorer les filtres

### Fonctionnement actuel

```text
DAX récupère un périmètre large
        ↓
Python charge le résultat
        ↓
pandas applique les filtres
```

### Fonctionnement recommandé à terme

```text
Utilisateur choisit les filtres
        ↓
Python construit une requête DAX filtrée
        ↓
Power BI renvoie seulement le périmètre nécessaire
```

Exemple conceptuel :

```DAX
EVALUATE
CALCULATETABLE(
    SUMMARIZECOLUMNS(
        'Date'[Month],
        Product[Category],
        'Sales Territory'[Group],
        'Sales Order'[Channel],
        "Sales", [Sales],
        "Cost", [Cost],
        "Profit", [Profit],
        "Orders", [Orders]
    ),
    TREATAS({"Internet"}, 'Sales Order'[Channel]),
    TREATAS({"Bikes"}, Product[Category]),
    TREATAS({"Europe"}, 'Sales Territory'[Group])
)
```

### Sécurité des filtres

Ne jamais concaténer directement une valeur utilisateur dans une expression DAX.

Utiliser :

- une liste blanche des dimensions autorisées ;
- un échappement des apostrophes ;
- une validation des valeurs ;
- un rejet des colonnes inconnues ;
- aucune expression DAX libre dans l'interface.

Exemple :

```python
ALLOWED_FILTERS = {
    "channel": "'Sales Order'[Channel]",
    "category": "Product[Category]",
    "group": "'Sales Territory'[Group]",
}
```

---

## 12. Gérer le refresh du dataset

L'application ne doit pas rafraîchir le modèle à chaque filtre.

Le processus recommandé est :

```text
Source de données
        ↓
Refresh planifié Power BI
        ↓
Dataset actualisé
        ↓
Application lit les données disponibles
```

Exemple :

```text
02:00 : refresh du dataset
02:15 : contrôle de qualité
02:30 : données disponibles dans l'application
```

L'application doit uniquement lire le modèle publié. Elle ne doit pas :

- ouvrir Power BI Desktop ;
- modifier le modèle ;
- gérer directement le fichier source ;
- lancer un refresh complet pour chaque utilisateur.

---

## 13. Gestion des erreurs

Le connecteur Service doit distinguer les erreurs.

### HTTP 401

Token absent, invalide ou expiré.

Actions :

- renouveler le token ;
- vérifier le tenant ;
- vérifier le client ID ;
- vérifier le secret ou le certificat.

### HTTP 403

Identité authentifiée mais non autorisée.

Actions :

- vérifier l'accès au workspace ;
- vérifier les droits sur le dataset ;
- vérifier les paramètres du tenant ;
- vérifier la sécurité RLS.

### HTTP 404

Workspace ou dataset incorrect.

Action :

- vérifier les identifiants de l'environnement courant.

### HTTP 429

Limite de fréquence atteinte.

Actions :

- retry avec délai exponentiel ;
- cache ;
- limitation du nombre de requêtes ;
- regroupement des requêtes.

### HTTP 5xx

Erreur temporaire du service.

Actions :

- retry limité ;
- journalisation ;
- affichage d'un message d'erreur explicite.

Une erreur d'authentification ne doit jamais être transformée en `No data available`.

---

## 14. Déploiement par environnement

### Développement

```text
Power BI Desktop
Python local
.env local
```

### Test

```text
Power BI Service - Workspace BI-Test
Service principal de test
Variables secrètes CI/CD
```

### Production

```text
Power BI Service/Fabric - Workspace BI-Prod
Identité de production
Key Vault
Logs centralisés
Monitoring
```

Les identifiants des datasets peuvent être différents selon l'environnement.

Les configurations doivent donc être séparées :

```text
config.dev.json
config.test.json
config.prod.json
```

Ces fichiers ne doivent pas contenir de secrets.

---

## 15. Tests nécessaires

### Tests unitaires

Tester :

- conversion JSON vers DataFrame ;
- renommage des colonnes ;
- conversion des dates ;
- application des filtres ;
- génération de la requête DAX ;
- gestion des valeurs nulles ;
- calcul des KPI ;
- calcul des anomalies.

### Tests d'intégration

Tester :

- authentification Entra ID ;
- accès au workspace ;
- appel `executeQueries` ;
- conversion de la réponse ;
- accès au dataset réel.

### Tests de contrat Power BI

Vérifier automatiquement que les mesures suivantes existent :

```text
Sales
Cost
Profit
Orders
```

Et que les dimensions suivantes existent :

```text
Date[Month]
Product[Category]
Sales Territory[Group]
Sales Order[Channel]
```

### Test de déploiement

Avant chaque promotion en production :

1. exécuter une requête DAX minimale ;
2. vérifier que le dataset répond ;
3. vérifier le nombre de lignes ;
4. vérifier les dates minimale et maximale ;
5. vérifier les valeurs nulles ;
6. vérifier les KPI principaux ;
7. comparer le résultat avec Power BI Desktop ;
8. vérifier qu'aucune mesure n'a changé de nom.

---

## 16. Plan de migration par phases

### Phase 1 — Stabiliser le projet actuel

- corriger le fournisseur `mock` manquant ;
- séparer les tests live des tests unitaires ;
- ajouter une validation complète du modèle ;
- supprimer les chemins absolus ;
- documenter la configuration Desktop ;
- garder Power BI Desktop comme mode de développement.

### Phase 2 — Ajouter le mode Power BI Service

Créer :

```text
src/connectors/powerbi_desktop.py
src/connectors/powerbi_service.py
src/connectors/factory.py
```

Conserver temporairement les deux modes :

```dotenv
POWERBI_MODE=desktop
```

ou :

```dotenv
POWERBI_MODE=service
```

### Phase 3 — Publier le dataset

- publier le PBIP dans `BI-Dev` ;
- configurer une source portable ;
- tester le refresh ;
- récupérer le dataset ID ;
- configurer l'identité applicative ;
- tester l'accès en lecture seule.

### Phase 4 — Valider l'API

- exécuter la requête DAX via REST API ;
- comparer le résultat avec Desktop ;
- comparer les KPI ;
- comparer les anomalies ;
- vérifier les dates et le nombre de lignes.

### Phase 5 — Optimiser les filtres

Commencer avec :

```text
requête large + filtre pandas
```

Puis migrer vers :

```text
filtres intégrés dans la requête DAX
```

Cette optimisation doit être réalisée lorsque le volume de données le justifie.

### Phase 6 — Déployer

- environnement Python reproductible ;
- secrets dans Key Vault ;
- application Streamlit ou service web ;
- logs centralisés ;
- monitoring ;
- workspace Power BI de production ;
- procédure de rollback.

---

## 17. Résultat attendu

L'architecture finale doit ressembler à ceci :

```text
Utilisateur
    ↓
Application déployée
    ↓
Authentification Entra ID
    ↓
Power BI REST API ou XMLA
    ↓
Dataset Power BI Service/Fabric
    ↓
DAX filtré
    ↓
KPI et anomalies
    ↓
Rapport validé
```

Power BI Desktop ne sera plus nécessaire pour utiliser l'application. Il servira uniquement à :

- modifier le modèle ;
- créer ou modifier les mesures ;
- concevoir les visuels ;
- publier une nouvelle version vers le workspace de développement.

