# Guide de mise en production de l'ERP ATR

Ce guide décrit, dans l'ordre, ce qu'il faut faire pour passer de la démonstration à l'utilisation réelle sur le
serveur de l'entreprise. Chaque étape renvoie à la rubrique du `README.md` qui la détaille.

Durée indicative : une demi-journée pour l'installation, puis une à deux journées de chargement des données et de
création des comptes, puis une période de fonctionnement en parallèle de IE.

## 1. Avant de commencer

- [ ] **Passer le dépôt GitHub en privé** (Settings, General, Danger Zone, Change visibility). Tant qu'il est public,
      n'y déposer aucun fichier de l'entreprise (clients, personnel, stock, sauvegardes, fichier `.env`).
- [ ] Désigner la personne qui administre l'ERP (création des comptes, mises à jour, sauvegardes) et son suppléant.
- [ ] Rassembler les fichiers Excel de départ : fournisseurs, clients, articles et stock, parc de matériels, personnel,
      projets et codes analytiques. Ils restent sur un poste de l'entreprise, jamais dans le dépôt.
- [ ] Rassembler les images de signature des valideurs des bons de commande (responsable achats, contrôleur de gestion).

## 2. Le serveur

Configuration conseillée pour moins de 100 utilisateurs : 4 cœurs, 8 Go de mémoire, 100 Go de disque, et un second
disque ou un partage réseau pour la copie des sauvegardes.

- [ ] Windows Server 2019 ou plus récent, ou Windows 10/11 Professionnel, à jour.
- [ ] Installer Docker Desktop (avec WSL 2) et le régler pour démarrer avec Windows.
- [ ] Installer Git pour Windows, puis récupérer le projet dans un dossier simple, par exemple `C:\erp-atr`.
- [ ] Donner au serveur une adresse fixe sur le réseau et, si possible, un nom (par exemple `erp.atr.local`).
- [ ] Ouvrir le port 80 dans le pare-feu de Windows pour le réseau de l'entreprise.

## 3. Installation

Détail : README, « Installer sur le serveur ».

- [ ] Copier `.env.example` en `.env` et renseigner :
  - `SECRET_KEY` : une longue chaîne aléatoire (50 caractères ou plus) ;
  - `POSTGRES_PASSWORD` : un mot de passe propre à ce serveur ;
  - `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS` : le nom et l'adresse du serveur ;
  - `DEBUG=False` ;
  - `COPIE_VERS` : le dossier de copie des sauvegardes, sur un autre disque ;
  - pour les rappels par e-mail : `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`,
    `ADRESSE_ERP` (README, « Rappels par e-mail »).
- [ ] Garder une copie du fichier `.env` en lieu sûr, hors du serveur.
- [ ] Lancer `docker compose up -d --build`.
- [ ] Créer le compte administrateur : `docker compose exec backend python manage.py createsuperuser`.
- [ ] Ouvrir `http://<nom du serveur>/` depuis un autre poste et se connecter.

Ne pas lancer `demarrer-demo.bat` ni la commande `donnees_demo` sur le serveur : ils servent uniquement à la
démonstration sur un poste.

## 4. Paramétrage

Dans l'administration (`http://<nom du serveur>/admin/`) puis dans l'ERP :

- [ ] Fiche Société : coordonnées, logo, taux de TVA, seuil de validation par la direction générale.
- [ ] Administration, « Sites et services » : vérifier les quatre sites, les services, et désigner le responsable de
      chaque service (sans responsable, les demandes du service restent bloquées).
- [ ] Magasins de stock et emplacements (administration).
- [ ] Lignes budgétaires de l'exercice : Achats, « Suivi du budget » (contrôle de gestion).

## 5. Comptes et rôles

Détail : README, « Comptes des utilisateurs et rôles » et la rubrique de chaque module.

- [ ] Créer un compte par personne dans Administration, « Comptes ». Chaque personne choisit son mot de passe à sa
      première connexion.
- [ ] Donner à chacun les rôles de son poste. Repères :

| Poste | Rôles à donner |
| --- | --- |
| Tout salarié qui utilise l'ERP | Achats - Demandeur, Stock - Demandeur, Moyens généraux - Demandeur, RH - Salarié, HSE - Déclarant |
| Responsable d'un service | les rôles ci-dessus, et être désigné responsable du service |
| Acheteur | Achats - Acheteur |
| Responsable achats | Achats - Responsable achats |
| Directeur technique | Achats - Directeur technique, Technique - Consultation |
| Contrôleur de gestion | Achats - Contrôleur de gestion |
| Direction financière | Achats - Direction financière, Commercial - Validation finance, Direction - Tableau de bord |
| Direction générale | Achats - Direction générale, Commercial - Validation DG, Direction - Tableau de bord |
| Magasinier | Achats - Magasinier, Stock - Magasinier |
| Responsable du stock | Stock - Responsable |
| Mécanicien | Technique - Mécanicien |
| Chef d'atelier | Technique - Chef d'atelier |
| Commercial | Commercial - Commercial |
| Responsable commercial | Commercial - Responsable |
| Agent d'exploitation | Exploitation - Agent |
| Agent de transport | Transport - Agent |
| Gestionnaire RH | RH - Gestionnaire |
| Responsable HSE | HSE - Responsable, HSE - Visiteur |
| Gestionnaire des moyens généraux | Moyens généraux - Gestionnaire |
| Administrateur de l'ERP | Administration - Comptes |

Les rôles « Consultation » de chaque module donnent un accès en lecture seule à ceux qui doivent seulement voir.

- [ ] Charger l'image de signature des deux valideurs des bons de commande (fiche du compte, administration).

## 6. Chargement des données de départ

Dans cet ordre, depuis les écrans de l'ERP. Chaque import commence par une simulation qui liste les erreurs sans rien
enregistrer.

1. [ ] Fournisseurs puis clients (Achats, « Fournisseurs » ; Commercial, « Clients » ; bouton d'import).
2. [ ] Articles et stock de départ (Stock, « État du stock », import). Faire l'inventaire physique juste avant.
3. [ ] Parc de matériels (Technique, « Parc de matériels », import du classeur par site et par activité).
4. [ ] Personnel (RH, « Personnel », import).
5. [ ] Projets et codes analytiques : `docker compose exec backend python manage.py importer_projets <classeur>`.
6. [ ] Contrats et échéances des moyens généraux, plans d'entretien préventif : saisie dans les écrans.

## 7. Contrôle automatique

```
docker compose exec backend python manage.py verifier_installation
```

La commande ne modifie rien. Elle liste ce qui est prêt, les points bloquants (réglages de sécurité, société,
administrateur, comptes de démonstration) et les points d'attention (services sans responsable, rôles attribués à
personne, signatures absentes, données non chargées). Corriger jusqu'à ne plus avoir de point bloquant.

## 8. Sauvegardes

Détail : README, « Sauvegardes ».

- [ ] Lancer `sauvegarder.bat` une première fois et vérifier le dossier `sauvegardes` et la copie (`COPIE_VERS`).
- [ ] Lancer `planifier-sauvegarde.bat` en administrateur pour la sauvegarde de chaque nuit.
- [ ] Essayer `restaurer.bat` sur un autre poste avant d'en avoir besoin.

## 9. Recette avant ouverture

Dérouler chaque circuit une fois avec les vrais comptes, de bout en bout :

- [ ] Demande d'achat de pièce : demande, validation du responsable, attribution à un acheteur, bon de commande,
      validations, PDF signé, bon de réception, entrée en stock, facture fournisseur.
- [ ] Demande liée au budget : demande, validations selon le montant, consommation de la ligne budgétaire.
- [ ] Stock : demande de sortie avec numéro d'OR, bon de sortie, inventaire, transfert entre magasins.
- [ ] Technique : ordre de réparation, temps passé, pièces, clôture ; plein de carburant ; plan d'entretien.
- [ ] Commercial et exploitation : GO / NO GO, devis en PDF, mise à disposition, retour, relevé de location.
- [ ] Transport : ordre de transport, départ, livraison, synthèse des kilomètres.
- [ ] RH et HSE : demande de congé, événement HSE avec action corrective, visite de sécurité.
- [ ] Moyens généraux : demande d'intervention, échéance d'un contrat.
- [ ] Téléphone : ouvrir l'ERP sur un téléphone du réseau et l'installer sur l'écran d'accueil.

## 10. Ouverture et fonctionnement en parallèle de IE

- [ ] Former les utilisateurs par service (une heure par module suffit), en commençant par les Achats.
- [ ] Ouvrir module par module, dans l'ordre de la feuille de route : Achats et Moyens généraux, Stock et Technique,
      Commercial, Exploitation et Transport, puis RH et HSE.
- [ ] Pendant la période en parallèle : la facture de location reste émise dans IE à partir du relevé de location de
      l'ERP ; le numéro de l'ancien système se note dans le champ prévu sur les documents.
- [ ] Chaque semaine : lire le journal des sauvegardes (`sauvegardes\journal.txt`) et le tableau de bord de direction.

## 11. Accès depuis l'extérieur (téléphones hors du réseau)

À faire avec le service informatique, après l'ouverture en interne :

- [ ] Préférer un VPN d'entreprise. À défaut, publier l'ERP derrière un nom de domaine avec un certificat HTTPS.
      Ne jamais exposer le port 80 directement sur Internet.
- [ ] Ajouter le nom public à `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS`, puis relancer `docker compose up -d`.

## 12. Mises à jour

Détail : README, « Mettre à jour le serveur ».

- [ ] Lancer `mettre-a-jour.bat` : il sauvegarde, récupère la nouvelle version, redémarre et applique les migrations.
- [ ] Après une mise à jour qui annonce un nouveau rôle, l'attribuer dans « Comptes ».

## Limites connues

- Les scripts `.bat` et l'installation Docker n'ont pas encore été essayés sur le serveur réel : prévoir une première
  installation d'essai avant la date d'ouverture.
- Le module Finances n'est pas développé : la comptabilité et la facturation restent dans IE.
- Les rappels à l'écran fonctionnent sans réglage ; les rappels par e-mail demandent un serveur d'envoi.
