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
