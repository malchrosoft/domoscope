# Domoscope

**Scan, inventaire et pilotage des appareils de ton réseau local.**

Domoscope est un petit projet Python local qui :

- balaie le réseau interne (ping sweep + ARP) ;
- détecte les services (SSDP/UPnP, mDNS, broadcasts Tuya, Kasa, WiZ, LIFX, Yeelight, miIO) ;
- identifie les appareils (adresse MAC, fabricant, type, ports, nom) ;
- conserve un inventaire SQLite avec historique des scans ;
- génère des rapports HTML, JSON et CSV ;
- fournit une interface web locale (FastAPI) ;
- peut piloter les ampoules **Tuya / Smart Life** en local (dont **Superia Milano**) via `tinytuya`.

> Projet prévu pour **ton** réseau local. Ne le lance pas sur un réseau que tu ne possèdes pas.

## Démarrage rapide

```powershell
cd I:\Dev\DEVELOPPEMENT\domoscope
uv sync --extra tuya

uv run domoscope init
uv run domoscope scan
uv run domoscope serve
```

Puis ouvrir <http://127.0.0.1:8765>.

Alternative avec le script fourni :

```powershell
.\run.ps1 scan
.\run.ps1 serve
```

## Commandes

| Commande | Effet |
|---|---|
| `uv run domoscope init` | Crée la base SQLite et la clé de chiffrement |
| `uv run domoscope scan` | Scanne le réseau et met à jour l’inventaire |
| `uv run domoscope scan --subnet 192.168.0.0/24` | Force un sous-réseau |
| `uv run domoscope devices` | Liste les appareils connus |
| `uv run domoscope report --format html` | Génère `data/reports/domoscope-*.html` |
| `uv run domoscope report --format json --output inventaire.json` | Export JSON |
| `uv run domoscope serve` | Lance l’interface web locale |

## Interface web

- `/` : tableau de bord et liste des appareils
- `/devices/{id}` : fiche détaillée, notes, identifiants Tuya, pilotage
- `/report` : rapport imprimable
- `/api/devices` : inventaire JSON
- `/api/scan` : scan en POST
- `/api/health` : état du service

## Configuration

Les variables sont lues dans l’environnement (voir `.env.example`) :

| Variable | Défaut | Rôle |
|---|---|---|
| `DOMOSCOPE_DB` | `data/domoscope.db` | Base SQLite |
| `DOMOSCOPE_SUBNET` | auto | Force le sous-réseau à scanner |
| `DOMOSCOPE_HOST` | `127.0.0.1` | Écoute web |
| `DOMOSCOPE_PORT` | `8765` | Port web |
| `DOMOSCOPE_ONLINE_LOOKUP` | `0` | Recherche OUI en ligne (macvendors.com) |
| `DOMOSCOPE_TUYA_VERSION` | `3.3` | Version du protocole Tuya |
| `DOMOSCOPE_SECRET_KEY` | généré | Clé de chiffrement des secrets |

## Pilotage des ampoules Superia Milano

Les ampoules **Superia Milano SMART RGB + White** sont des appareils **Tuya / Smart Life**. Domoscope les détecte grâce au port local **6668** et à la MAC du fabricant.

Pour les piloter, il faut renseigner dans la fiche de l’appareil :

1. le **Device ID** ;
2. la **Local Key** ;
3. éventuellement la **version du protocole** (souvent `3.3`).

Pour récupérer ces valeurs, le plus simple est `tinytuya` :

```powershell
uv pip install tinytuya
uv run python -m tinytuya wizard
```

Le wizard demande les identifiants du **Tuya IoT Platform** (gratuit), scanne le réseau et génère un `devices.json` avec les Device ID et Local Keys. Recopie ensuite les valeurs dans la fiche Domoscope.

> La Local Key est chiffrée en base avec `cryptography` (clé générée dans `data/secret.key`). Ne partage jamais ce fichier ni la base.

## Architecture

```text
src/domoscope/
├─ network.py      # interfaces, ping sweep, ARP, scan TCP
├─ discovery.py    # SSDP, mDNS, broadcasts Tuya/Kasa/WiZ/LIFX/Yeelight/miIO
├─ identify.py     # heuristiques de type d’appareil
├─ vendor.py       # table OUI locale + lookup optionnel
├─ scanner.py      # orchestration d’un scan
├─ models.py       # Device / ScanSummary
├─ db.py           # SQLite, upsert, historique
├─ secrets.py      # chiffrement des clés locales
├─ drivers/
│  ├─ base.py
│  └─ tuya.py      # pilotage local Tuya
├─ reporting.py    # rapports HTML/JSON/CSV
├─ web.py          # FastAPI
└─ templates/      # UI et rapport
```

## Sécurité

- Par défaut, **aucune donnée ne part vers le cloud**.
- Le scan est **lecture seule** ; le pilotage n’est actif que pour les appareils dont tu as saisi les identifiants.
- Les secrets sont chiffrés avec une clé locale `data/secret.key` (à sauvegarder, sinon les clés Tuya deviennent illisibles).
- L’interface web écoute sur `127.0.0.1` par défaut. Si tu l’exposes sur le LAN, ajoute une authentification et HTTPS.
- N’utilise pas Domoscope pour scanner un réseau qui ne t’appartient pas.

## Limites connues

- Les appareils **cloud-only** (Home Connect/BSH, certains Xiaomi, Tuya sans clé locale) sont détectés mais pas pilotables.
- Le mDNS dépend du pare-feu Windows et de la configuration du réseau ; certains appareils ne répondent qu’en multicast.
- Les scans ping/ARP peuvent manquer les appareils qui bloquent l’ICMP ou sont en veille.
- Le pilotage Tuya nécessite `tinytuya` et une clé locale valide.

## Feuille de route

- [ ] Authentification de l’interface web
- [ ] Planificateur de scans (APScheduler)
- [ ] Notifications de nouveaux appareils
- [ ] Pilotes Hue, Shelly, Kasa, ESPHome, Home Connect
- [ ] Export PDF
- [ ] Intégration MQTT Discovery pour exposer les appareils à Home Assistant

## Licence

[PolyForm Noncommercial License 1.0.0](LICENSE.md), identifiant SPDX
`PolyForm-Noncommercial-1.0.0` (non approuvée OSI).

- **Autorisé sans frais** : usage personnel, hobby, recherche, association, enseignement,
  organisme public. Le fork et la modification sont permis.
- **Obligatoire en cas de fork** : conserver la licence et la ligne
  `Required Notice: Copyright (c) 2026 Aymeric MALCHROWICZ`. Un fork ne peut pas être
  relicencié ni revendu.
- **Interdit sans accord** : tout usage commercial, y compris l’usage interne en entreprise,
  l’intégration dans un produit payant, l’hébergement pour des tiers et la revente.

Une licence commerciale payante est disponible séparément : voir [COMMERCIAL.md](COMMERCIAL.md).
Les contributions externes ne sont acceptées que sous cession de droits explicite :
voir [CONTRIBUTING.md](CONTRIBUTING.md).

> Le bouton « Fork » de GitHub reste disponible sur un dépôt public : la licence encadre
> l’usage et la redistribution, pas l’acte de forker.

