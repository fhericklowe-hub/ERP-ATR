# ERP

ERP sur mesure : Achats, Moyens généraux, Stock et logistique, Technique, Commercial, Exploitation, RH, HSE, Finances.

## Organisation du dépôt

| Dossier | Contenu |
| --- | --- |
| `backend/` | API Django. Un dossier par module dans `backend/apps/`. |
| `backend/apps/core/` | Socle : utilisateurs, sites, services, droits. |
| `backend/apps/referentiels/` | Données partagées : tiers (clients, fournisseurs), emplacements, articles. |
| `backend/apps/achats/` | Achats : demandes d'achat et circuit de validation. |
| `frontend/` | Application web React, installable sur téléphone (PWA). |
| `docker-compose.yml` | Installation complète : PostgreSQL, Redis, API, tâches de fond, Nginx. |

## Développer sur son poste

Backend (SQLite par défaut, rien d'autre à installer) :

```
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows ; sous Linux/macOS : source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Frontend, dans un second terminal :

```
cd frontend
npm install
npm run dev
```

L'application est sur http://localhost:5173, l'administration sur http://localhost:8000/admin/
et la documentation de l'API sur http://localhost:8000/api/docs/.

Tests : `python manage.py test` dans `backend/`.

## Installer sur le serveur

```
copy .env.example .env          # puis remplacer SECRET_KEY, les mots de passe et ALLOWED_HOSTS
docker compose up -d --build
docker compose exec backend python manage.py createsuperuser
```

L'application répond ensuite sur le port 80 du serveur.

## Droits

Les rôles sont les groupes Django, gérés dans l'administration. Chaque rôle reçoit des droits
voir, ajouter, modifier et supprimer par type d'objet. L'API refuse toute lecture ou écriture
sans le droit correspondant.

## Achats : demande d'achat

Circuit : brouillon, validation par le responsable du service demandeur (désigné sur le service dans
l'administration), validation par le directeur technique si l'urgence est de niveau 1, puis traitement
par les achats.

Le délai d'émission du bon de commande (4 h ouvrées, 2 ou 3 jours ouvrés selon l'urgence) démarre à la
réception de la fiche complète par les achats. Horaires de travail : du lundi au vendredi de 8 h à 12 h
et de 13 h à 17 h, le samedi de 8 h à 12 h, hors jours fériés. Les délais en jours ne comptent pas le
samedi (voir `backend/apps/achats/delais.py`).

À son arrivée aux achats, la demande est attribuée automatiquement à l'acheteur disponible qui a le moins
de demandes en cours. L'acheteur contrôle la fiche et le stock, et peut la renvoyer au demandeur ; le
responsable achats valide ou refuse, et peut réattribuer. Les acheteurs et leur disponibilité se gèrent
dans l'administration (Achats > Acheteurs).

Quatre rôles sont créés à l'installation : « Achats - Demandeur », « Achats - Directeur technique »,
« Achats - Acheteur » et « Achats - Responsable achats ».

## Achats : bon de commande

Un bon de commande se crée depuis une demande d'achat validée et reprend ses articles. Il est validé
dans l'application par le responsable achats, puis par le contrôleur de gestion, dans cet ordre. Un
refus le renvoie à l'acheteur pour correction. Une fois validé deux fois, son PDF peut être imprimé,
signé et transmis au fournisseur ; avant, le PDF porte la mention PROJET.

Les montants sont arrondis au franc. La TVA se règle par ligne (18 % par défaut). Les coordonnées et le
logo imprimés se renseignent dans l'administration (Socle > Société). Les fournisseurs se créent dans
l'administration (Référentiels > Tiers).

Rôle supplémentaire : « Achats - Contrôleur de gestion ».

## Achats : demandes liées au budget

Frais généraux, sous-traitance et investissements suivent un circuit plus long que les pièces techniques :
responsable du service, accord de la direction générale (investissement ou hors budget), consultation des
fournisseurs par les achats, puis responsable achats, contrôle de gestion, direction financière et, selon le
cas, direction générale (investissement, montant au-dessus du seuil, hors budget ou dépassement de la ligne).

- Le seuil (1 000 000 par défaut) se règle dans l'administration, fiche Société.
- Les lignes budgétaires se saisissent dans l'administration ou par l'API (rôle contrôleur de gestion).
- Les comptes de charge sont créés à l'installation. Les projets et codes analytiques se chargent depuis le
  classeur de l'entreprise, qui ne doit pas être ajouté au dépôt :
  `python manage.py importer_projets chemin/vers/le-classeur.xlsx`

## Moyens généraux : biens et demandes d'intervention

- **Inventaire des biens** (bâtiments et locaux, véhicules de service, mobilier, informatique, téléphonie,
  équipements) : numéro `MG-00001`, site, emplacement, service utilisateur, état (en service, en panne,
  en réparation, réformé), date et valeur d'acquisition.
- **Demande d'intervention** (`INT-2026-0001`) : tout utilisateur signale un problème (objet, catégorie,
  priorité, site, lieu, bien concerné). Les moyens généraux la prennent en charge (intervenant interne ou
  prestataire, date prévue), déclarent l'intervention réalisée (compte rendu, coût), puis le demandeur
  confirme et clôture, ou rouvre la demande si le problème persiste. Une demande peut être refusée avec motif.
- L'état du bien suit la demande : en panne à la déclaration si le demandeur le coche, en réparation à la
  prise en charge, en service à la réalisation.

Deux rôles sont créés à l'installation : « Moyens généraux - Demandeur » et « Moyens généraux - Gestionnaire ».
Le menu de l'application n'affiche que les rubriques auxquelles l'utilisateur a droit.

## Moyens généraux : contrats et échéances

- **Contrats** (`CTR-2026-0001`) : assurances, baux, maintenance, gardiennage, nettoyage, abonnements. Prestataire,
  référence, site ou bien concerné, dates, préavis, tacite reconduction, montant et périodicité.
- **Échéances** : assurance, visite technique, vignette et taxes, contrôle réglementaire, loyer, fin de contrat.
  Chaque échéance a un délai de rappel (30 jours par défaut) et peut revenir tous les N mois. L'écran s'ouvre sur
  ce qui est à traiter : en retard ou dans le délai de rappel. Marquer une échéance faite crée la suivante.
- Un contrat avec une date de fin crée et tient à jour son échéance « fin de contrat », placée à la date limite
  du préavis.

Ces écrans sont réservés au rôle « Moyens généraux - Gestionnaire ».

## Pièces jointes

Un fichier (devis, facture, bon de livraison, contrat signé, photo) se joint à une demande d'achat, une demande
liée au budget, un bon de commande, un bon de réception, une demande d'intervention ou un contrat.

- Les droits sont ceux du document : qui le voit peut ouvrir ses pièces, qui peut le modifier peut en ajouter.
  Seule la personne qui a ajouté une pièce peut la retirer.
- Types acceptés : PDF, images JPG et PNG, Word, Excel, CSV, texte, e-mail. 10 Mo au plus par fichier.
- Les fichiers sont rangés dans `media/pieces/` sous un nom aléatoire. Ils ne s'ouvrent que par l'API ; Nginx
  refuse l'accès direct à ce dossier. **Ce dossier doit être compris dans les sauvegardes.**
- Un nouveau module déclare ses documents par `pieces.declarer(SaVue)` dans son `apps.py`.

## Stock : magasins, entrées et sorties

- **Magasins** : un par site (ce sont les emplacements de type « site » des référentiels).
- **Le stock est la somme des mouvements.** Un mouvement ne se modifie pas et ne se supprime pas ; une erreur se
  corrige par une annulation ou un ajustement d'inventaire.
- **Entrées** : à la validation d'un bon de réception, la « quantité à mettre en stock » entre dans le magasin du
  site de la commande, pour les lignes qui portent un article du catalogue géré en stock. Annuler le bon de
  réception ressort les pièces, sauf si elles sont déjà sorties.
- **Bon de sortie** (`BS-2026-0001`) : n° d'OR obligatoire, matériel, magasin, personne à qui les pièces sont
  remises. Refusé si le stock du magasin ne suffit pas. Il ne se modifie pas ; le responsable du stock l'annule.
- **Inventaire** : le responsable met le stock à la quantité comptée, avec un motif. C'est aussi la façon de
  saisir le stock de départ. **Transfert** d'un magasin à un autre. **Seuil d'alerte** et rangement par article
  et par magasin.

Rôles créés à l'installation : « Stock - Consultation », « Stock - Magasinier », « Stock - Responsable ».

### Bon de sortie en PDF et import du stock

- Le bon de sortie s'imprime en PDF, avec le visa du magasinier et celui du receveur.
- **Import depuis Excel** (écran Stock, réservé au responsable) : première feuille, titres en première ligne :
  `Code, Désignation, Unité, Quantité`, puis au besoin `Seuil, Rangement, Prix`. Les articles inconnus sont créés,
  le stock du magasin est mis à la quantité du fichier, les articles absents du fichier ne sont pas touchés.
  Le fichier est d'abord contrôlé ; une seule ligne en erreur et rien n'est importé.
- La même chose en ligne de commande :
  `python manage.py importer_stock stock.xlsx --magasin SIEGE --utilisateur <identifiant> [--simuler]`.

### Demande de sortie de stock

- Un atelier ou un service demande des articles au magasin (`DS-2026-0001`) : articles et quantités, n° d'OR,
  matériel, service, magasin, usage.
- **Le n° d'OR est obligatoire dès qu'une pièce détachée est demandée.** Une fourniture ou un consommable sort
  sans OR : les fournitures de bureau passent par ce même circuit.
- Le responsable du service valide (étape sautée si le service n'a pas de responsable ou si c'est lui qui
  demande), puis le magasin sert : il voit le stock, ajuste les quantités, et le bon de sortie est créé.
  Ce qui n'est pas servi fait l'objet d'une nouvelle demande.
- Rôle « Stock - Demandeur », à donner à tous ceux qui demandent des pièces ou des fournitures.

## Technique : parc de matériels et ordres de réparation

- **Parc** : engins de manutention et de levage, camions, remorques, véhicules, groupes. N° de parc, type,
  marque, modèle, série, immatriculation, capacité, activité, site de rattachement, lieu où il se trouve
  (site ou client), état, compteurs heures et kilomètres.
- **Ordre de réparation** (`OR-2026-0001`) : ouvert par un mécanicien ou le chef d'atelier sur un matériel
  (panne, entretien, accident, modification). Démarrage avec diagnostic et relevé de compteur, fin des travaux
  avec compte rendu, clôture par le chef d'atelier, qui peut aussi affecter, rouvrir et annuler.
- **État du matériel** : « en panne » à l'ouverture d'un OR immobilisant, « en réparation » au démarrage,
  « disponible » quand il n'y a plus d'OR immobilisant ouvert. Le compteur relevé met la fiche à jour.
- **Pièces** : l'OR liste les pièces sorties du stock sous son numéro. Depuis l'OR, « Demander des pièces au
  magasin » ouvre une demande de sortie déjà remplie. Les OR ouverts sont proposés à la saisie du n° d'OR.

Rôles créés à l'installation : « Technique - Consultation », « Technique - Mécanicien », « Technique - Chef d'atelier ».

## Rappels par e-mail

Du lundi au samedi à 7 h 30, chaque personne qui a une adresse e-mail sur sa fiche utilisateur reçoit ce qui attend
son action, selon ses droits :

- les échéances des moyens généraux en retard ou dans leur délai de rappel (qui traite les échéances) ;
- les entretiens préventifs à faire ou bientôt à faire, et les ordres de réparation à clôturer (chef d'atelier) ;
- les articles au seuil d'alerte ou en dessous (responsable du stock).

Celui qui n'a rien à traiter ne reçoit rien. L'envoi est fait par le service `worker`.

Réglages, dans le fichier `.env` du serveur : `EMAIL_HOST`, `EMAIL_PORT` (587), `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` (true), `DEFAULT_FROM_EMAIL` (expéditeur) et `ADRESSE_ERP` (adresse de
l'application, rappelée en bas du message). Tant que `EMAIL_HOST` est vide, rien ne part : les messages s'écrivent
dans le journal du service `worker`. Ne mettez jamais ces valeurs dans le dépôt.

Pour voir qui recevrait quoi sans rien envoyer : `python manage.py envoyer_rappels --simuler`. Sans `--simuler`, la
commande envoie tout de suite.

Un module ajoute ses rappels avec `rappels.declarer(fonction)` dans son `apps.py` (voir `apps/core/rappels.py`).
