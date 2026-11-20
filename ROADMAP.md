# Feuille de route

État du projet et travail prévu. Cocher les cases au fil des commits.

## Fait

- [x] Le scan conserve le nom et le type saisis à la main (`manual_fields`)
- [x] Tous les ports utilisés par l'identification sont scannés (dont 445/SMB)
- [x] Sonde LIFX GetService conforme (36 octets)
- [x] Lancement complet en une commande : `uv run domoscope` (base, premier scan, interface)
- [x] Installable comme outil : `uv tool install git+https://github.com/malchrosoft/domoscope`
- [x] Données dans le dossier utilisateur une fois installé (`DOMOSCOPE_HOME` pour forcer)
- [x] `DOMOSCOPE_SECRET_KEY` réellement lue, et refusée si ce n'est pas une clé Fernet
- [x] Simplification : code mort retiré, sondes UDP factorisées, liste des protocoles et port Tuya
      centralisés, appels système factorisés, plus d'effets de bord à l'import
- [x] Un seul scan à la fois (scan au démarrage et bouton « Scanner »)
- [x] Pilotage Tuya : luminosité et température en pourcentage (les valeurs brutes allaient de
      10 à 1000), bascule lue sur le bon point de données selon l'ampoule, timeouts courts

## Onglet « Domotique »

Un onglet dédié aux appareils **pilotables**, distinct de l'inventaire réseau : n'y figurent que
les appareils authentifiés, prêts à l'emploi, et dont on sait qu'ils répondent encore.

### Contenu

- [x] Route `/domotique` et lien dans la barre de navigation
- [x] Une carte par appareil pilotable : nom, type, IP actuelle, état (allumé/éteint,
      luminosité, couleur)
- [ ] Image et pièce sur la carte (voir « Images des appareils »)
- [x] Actions rapides sur la carte : allumer/éteindre, luminosité, couleur
- [x] Appareils détectés comme pilotables mais sans identifiants listés à part (« à configurer »)
      avec un lien vers leur fiche

### Validité des identifiants

Un appareil n'est « prêt » que si sa dernière vérification a réussi. Une Local Key Tuya change
quand l'appareil est réappairé dans l'application Smart Life : une clé saisie peut donc devenir
invalide sans rien changer côté Domoscope.

- [x] Vérification de l'état via le driver (`TuyaDriver.check`)
- [x] Stocker le résultat : `check_status`, `check_error`, `checked_at`
- [x] Trois statuts affichés : **prêt**, **injoignable** (hors ligne, IP changée), **clé invalide**
- [x] Vérification à l'ouverture de l'onglet (en parallèle, 3 s au plus) et à la demande
- [ ] Suivre l'appareil par sa MAC : si le DHCP lui donne une nouvelle IP, la retrouver via la
      table ARP sans attendre un scan complet (aujourd'hui : statut « injoignable » jusqu'au scan)
- [ ] Vérification en arrière-plan (planificateur) pour que la page s'affiche sans attendre

### Plus tard

- [ ] Regrouper les appareils par pièce
- [ ] Interface commune des drivers (`status`, `command`, capacités) pour accueillir d'autres
      marques dans le même onglet

## Interface

Contrainte : tout reste servi en local (fichiers copiés dans `static/`, pas de CDN), sans étape
de build JavaScript, pour garder la promesse « aucune donnée envoyée dans le cloud ».

- [ ] [htmx](https://htmx.org) : rafraîchir une carte ou un statut sans recharger la page
      (état des ampoules, progression du scan), transitions entre états
- [ ] [Alpine.js](https://alpinejs.dev) pour les petites interactions locales (onglets, menus)
- [ ] Composants web prêts à l'emploi (Web Awesome, successeur de Shoelace) : curseur de
      luminosité, sélecteur de couleur, interrupteurs, sans framework
- [ ] View Transitions API (native au navigateur) pour animer le passage liste → fiche

### Images des appareils

Par ordre de priorité, toutes téléchargées une fois puis mises en cache dans `data/images/` :

- [ ] **UPnP** : la description XML pointée par `LOCATION` (déjà stockée par le scan) contient
      souvent une `iconList` fournie par l'appareil lui-même — source locale, la meilleure
- [ ] **Tuya** : le `devices.json` produit par `tinytuya wizard` contient l'URL de l'image du
      produit (`icon`) ; l'importer avec le Device ID et la Local Key. Téléchargement depuis le
      CDN Tuya : désactivé par défaut, comme `DOMOSCOPE_ONLINE_LOOKUP`
- [ ] **Repli** : une icône par type d'appareil (ampoule, prise, imprimante, NAS…) tirée d'un jeu
      d'icônes libre embarqué (Lucide, licence ISC)
- [ ] Logo du fabricant en badge (Simple Icons, CC0 — attention au droit des marques)

## Packaging et distribution

- [ ] Publier sur PyPI (`uvx domoscope` / `pipx install domoscope`), version tirée du tag git
- [ ] Windows : exécutable autonome (PyInstaller) et démarrage comme service
- [ ] Image Docker — limite : le scan exige `network_mode: host`, que Docker Desktop
      (Windows, macOS) ne fournit pas vraiment ; viser Linux / Raspberry Pi / NAS
- [ ] Interface web installable sur téléphone (PWA : manifeste + icônes), sans code supplémentaire

### Application Android (Flutter)

Flutter (Dart) ne peut pas réutiliser le code Python : pour ne rien dupliquer, l'application
est un **client de l'API** d'un serveur Domoscope tournant sur le réseau (PC, NAS, Raspberry Pi).
Faire tourner le scan sur le téléphone n'est pas une option : Android interdit la lecture de la
table ARP depuis Android 10 et restreint ping et multicast.

- [ ] API JSON complète pour le pilotage (aujourd'hui des formulaires HTML) : `POST
      /api/devices/{id}/command`, mise à jour d'un appareil
- [ ] Schéma OpenAPI (fourni par FastAPI) comme contrat, client Dart généré à partir de lui
- [ ] Authentification par jeton (prérequis : l'API est alors exposée sur le LAN)
- [ ] Découverte du serveur par mDNS (`_domoscope._tcp`)

## Sécurité

- [ ] Authentification de l'interface web
- [ ] Protection CSRF des routes `POST` (une page web tierce peut sinon piloter les appareils)

## Fiabilité de la découverte

- [ ] Éviter les doublons quand un appareil est vu d'abord sans MAC puis avec
- [ ] Découverte Tuya : écouter les broadcasts des appareils (UDP 6666/6667) au lieu d'y envoyer
      une requête
- [ ] Tester `_parse_ipconfig` sur des sorties réelles (FR et EN)

## Fonctionnalités

- [ ] Planificateur de scans (APScheduler)
- [ ] Notifications de nouveaux appareils
- [ ] Pilotes Hue, Shelly, Kasa, ESPHome, Home Connect
- [ ] Export PDF
- [ ] Intégration MQTT Discovery pour exposer les appareils à Home Assistant
