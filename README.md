# ERP

ERP sur mesure : Achats, Moyens généraux, Stock et logistique, Technique, Commercial, Exploitation, RH, HSE, Finances.

## Organisation du dépôt

| Dossier | Contenu |
| --- | --- |
| `backend/` | API Django. Un dossier par module dans `backend/apps/`. |
| `backend/apps/core/` | Socle : utilisateurs, sites, services, droits. |
| `backend/apps/referentiels/` | Données partagées : tiers (clients, fournisseurs), emplacements, articles. |
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
