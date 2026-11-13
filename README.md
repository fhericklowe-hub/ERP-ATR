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

## Démonstration sur un poste Windows

1. Installer [Python 3.13](https://www.python.org/downloads/release/python-3139/) (« Windows installer 64-bit ») et
   [Node.js](https://nodejs.org) LTS. Une version plus récente de Python (3.15) ne convient pas encore ; elle peut
   rester installée à côté, le script choisit la bonne.
2. Télécharger le dépôt (bouton vert « Code », « Download ZIP ») et le décompresser.
3. Double-cliquer sur `demarrer-demo.bat`. La première fois, l'installation prend quelques minutes, puis l'ERP
   s'ouvre dans le navigateur sur http://localhost:5173.

Le script charge des données fictives (`manage.py donnees_demo`) : quelques fournisseurs, clients, articles en
stock, matériels, des documents en cours dans chaque module (une demande d'achat à valider, un bon de commande à
valider, un ordre de réparation, un devis envoyé, un presqu'accident, une visite de sécurité), et un compte par profil, tous avec le mot de passe `demo-atr` : `responsable` (tous les
modules), `controleur`, `acheteur`, `magasinier`, `chef`, `mecanicien`, `commercial`. La base reste dans
`backend/db.sqlite3` sur le poste ; la supprimer remet la démonstration à zéro. Cette commande refuse de tourner
sur la base du serveur.

## Installer sur le serveur

```
copy .env.example .env          # puis remplacer SECRET_KEY, les mots de passe et ALLOWED_HOSTS
docker compose up -d --build
docker compose exec backend python manage.py createsuperuser
```

L'application répond ensuite sur le port 80 du serveur.

## Fournisseurs et clients : écran et import depuis Excel

Achats, « Fournisseurs » et Commercial, « Clients » : recherche, création, modification. Une fiche ne se supprime pas,
elle se désactive (elle n'est alors plus proposée dans les listes). Sans code saisi, un numéro est attribué (T00001…).
Les contacts (nom, fonction, téléphone, e-mail) se tiennent dans la fiche, par ceux qui peuvent la modifier.
La fiche d'un client porte aussi ses sites (chantier, usine, dépôt) : ce sont les lieux proposés dans les mises à
disposition et dans le parc. Un site ne se supprime pas, il se désactive. Les sites de l'entreprise restent dans l'administration.

« Importer depuis Excel » (droit de créer et de modifier les tiers) : première feuille, titres en première ligne :
Raison sociale, puis au besoin Code, N° contribuable, Téléphone, E-mail, Adresse, Ville. Une fiche déjà connue (même
code, ou à défaut même raison sociale) est mise à jour, une case vide ne change rien ; les autres sont créées. On
contrôle d'abord le fichier : à la moindre ligne en erreur, rien n'est importé.

Le fichier des fournisseurs ou des clients ne doit jamais être déposé dans ce dépôt.

## Comptes des utilisateurs et rôles

Administration, « Comptes » : créer un compte, lui donner ses rôles, changer son mot de passe, le désactiver. Un compte
ne se supprime pas. La rubrique est réservée au rôle « Administration - Comptes » (droit `core.gerer_comptes`), à
attribuer une première fois dans l'administration Django, et aux administrateurs.

Garde-fous : on ne change pas ses propres rôles et on ne désactive pas son propre compte ; le compte d'un
administrateur (accès à l'administration Django) ne se modifie que par un administrateur, et cet écran n'en crée pas ;
un changement de mot de passe ferme les sessions ouvertes de ce compte. Celui qui tient ce rôle peut donner n'importe
quel rôle à un autre compte : ne le confier qu'à une ou deux personnes de confiance.

Chacun change son propre mot de passe en cliquant sur son nom, en haut à droite (« Mon compte ») : il donne
l'actuel, puis le nouveau deux fois. Ses autres appareils sont déconnectés.

Administration, « Sites et services » (même rôle, complété par la migration `core/0011`) : créer, corriger ou désactiver
un site ou un service, et désigner le **responsable de chaque service**, qui valide les demandes de ce service. L'écran
signale les services actifs sans responsable. Les magasins de stock restent dans l'administration Django.

## Catalogue des articles

Stock, « Articles » : recherche, création, modification. Un article ne se supprime pas, il se désactive. Deux codes
qui ne diffèrent que par les majuscules sont refusés. Le catalogue est tenu par les rôles « Stock - Responsable »,
« Achats - Acheteur » et « Achats - Responsable achats » (la migration `stock/0006` leur donne ce droit) ; les autres
continuent de le consulter depuis leurs écrans. L'import du stock de départ crée toujours les articles inconnus.

## RH : import du personnel depuis Excel

RH, Personnel, « Importer depuis Excel » (gestionnaire RH), ou en ligne de commande :

```
python manage.py importer_personnel personnel.xlsx --utilisateur <identifiant RH> [--simuler]
```

Première feuille, titres en première ligne : Nom, Prénoms, Site, puis au besoin Matricule, Sexe, Date de naissance,
Lieu de naissance, Nationalité, Téléphone, E-mail, Adresse, N° CNPS, Service, Fonction, Catégorie, Date d'embauche,
Solde de congés, Solde arrêté au. Un salarié déjà connu (même matricule, ou à défaut mêmes nom et prénoms) est mis à
jour, une case vide ne change rien ; les autres sont créés. On contrôle d'abord le fichier : à la moindre ligne en
erreur, rien n'est écrit. Le fichier du personnel ne doit jamais être déposé dans ce dépôt.

## Page d'accueil

À la connexion, chacun arrive sur une page « ce qui attend votre action » : demandes d'achat et bons de commande
à valider, demandes d'absence, actions HSE, échéances, alertes de stock, entretiens. Ce sont les mêmes rubriques que
le rappel quotidien par e-mail (`rappels.declarer` ; l'attribut `lien` d'une source donne l'écran où la traiter).
Le logo ramène à cette page.

## Tableau de bord de direction

Menu Direction, Tableau de bord : les chiffres clés de chaque module sur une page (demandes et commandes du mois,
valeur du stock, disponibilité du parc, devis du mois, effectifs et absences, accidents et actions en retard). Les
chiffres sont calculés à l'ouverture de la page (`backend/apps/core/pilotage.py`). La page est réservée au rôle
« Direction - Tableau de bord », qui ne donne aucun autre accès : à attribuer dans l'administration.

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

### Valeur du stock

Stock > Valeur du stock donne le stock valorisé au **coût moyen pondéré**, par article et par magasin, à la date
choisie, avec un export Excel. Chaque entrée chiffrée (bon de réception, stock de départ importé, ajustement avec un
prix) recalcule le coût moyen de l'article pour toute l'entreprise ; une sortie se fait à ce coût ; une entrée sans
prix entre au coût moyen du moment ; un transfert ne change rien. Les articles dont aucune entrée n'a de prix sont
signalés et ne sont pas comptés.

Le même écran donne la valeur des sorties sur une période, par service et par ordre de réparation.

Droit « Peut voir la valeur du stock et des consommations » : donné à « Stock - Responsable », « Achats - Responsable
achats » et « Achats - Contrôleur de gestion ».

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

## Commercial : devis de location

Le commercial saisit un devis (client, libellé, type de loyer, lignes avec quantité, prix, remise et durée). Un
matériel du parc peut être choisi sur une ligne. Circuit : brouillon, envoyé au client, puis accepté (le devis devient
la commande du client, avec son n° de bon de commande), refusé ou annulé. Un devis envoyé est figé ; « Reprendre » le
remet en brouillon. Sans date de validité, il est valable 30 jours.

Le PDF reprend le modèle de l'entreprise : « DEVIS » puis « COMMANDE CLIENT » une fois accepté, mention PROJET tant
qu'il est en brouillon, montant en lettres, cadres de signature.

Dans l'administration, Commercial > Réglages du commercial :

- **Conditions générales de location (PDF)** : le fichier est ajouté à la suite de chaque devis ;
- **Extrait des conditions** : le court texte imprimé en pied de première page ;
- **Validité d'un devis**, en jours.

Ces textes se chargent dans l'administration, ils ne sont pas dans le dépôt.

Rôles : « Commercial - Consultation », « Commercial - Commercial » (ses propres devis, création de clients) et
« Commercial - Responsable » (tous les devis, annulation d'une commande acceptée).

## Exploitation : mise à disposition du matériel

Sur un devis accepté, « Préparer la mise à disposition » crée une fiche par matériel du parc cité dans les lignes.
L'exploitation complète le lieu, les dates prévues, l'opérateur et les accessoires remis, puis enregistre :

- **la livraison** : personne qui reçoit le matériel chez le client, date, compteur, niveau de carburant. Le matériel
  doit être disponible ; il passe « en exploitation » chez le client ;
- **le retour** : personne qui le restitue, compteur, carburant, réserves sur l'état. Le matériel redevient
  disponible, et les heures utilisées sont calculées d'après les compteurs. S'il y a des réserves, la fiche propose
  d'ouvrir un ordre de réparation.

Un compteur ne peut pas être inférieur au dernier relevé du matériel. Une mise à disposition non livrée peut être
annulée avec un motif. Le bon de livraison et le bon de retour sortent en PDF, avec les cadres de signature ; les bons
signés et les photos se joignent à la fiche. Un retour prévu dépassé est signalé dans la liste.

Rôles : « Exploitation - Consultation » et « Exploitation - Agent ». Les rôles du Commercial voient les mises à
disposition de leurs devis.

## Commercial : relevé de location

Le relevé calcule ce qui est dû par le client sur une période. Ce n'est pas une facture : la facture reste émise dans
le logiciel de facturation, et son numéro est noté sur le relevé.

Sur une commande client, « Préparer le relevé de cette période » crée un brouillon :

- pour chaque matériel livré, la durée passée chez le client pendant la période, d'après les bons de livraison et de
  retour, dans l'unité du loyer (jours, semaines de 7 jours, mois ; un mois entamé compte au prorata sur 30 jours) ;
- les lignes sans matériel (transport, forfaits) une seule fois, sur le premier relevé ;
- avec un loyer au forfait, chaque matériel est relevé une seule fois.

Le commercial corrige les durées, quantités et remises ou retire une ligne. Le responsable commercial valide (« à
facturer »), puis le numéro et la date de la facture sont saisis (« facturé »). Deux relevés d'une même commande ne
peuvent pas se chevaucher ; un relevé annulé libère sa période. Le relevé sort en PDF.

Droits : les rôles Commercial préparent et corrigent, « Commercial - Responsable » valide et annule un relevé facturé,
les rôles Exploitation consultent.

## RH : dossiers du personnel

Chaque salarié a un dossier : état civil, coordonnées, personne à prévenir, n° CNPS, poste (site, service, fonction,
catégorie, responsable), date d'embauche, et le compte ERP qui lui correspond s'il en a un. Le matricule est
automatique s'il est laissé vide. Un salarié ne se supprime pas : on enregistre sa sortie des effectifs (date, motif).

Sur le dossier :

- les **contrats** successifs (CDI, CDD, stage, journalier, prestataire), avec la fin de période d'essai ;
- les **pièces à validité** : permis de conduire, autorisation de conduite d'engins, habilitations, visite médicale,
  pièce d'identité, carte de séjour ;
- les copies en pièces jointes.

RH > Échéances liste ce qui arrive à terme pour les salariés en poste : pièces à renouveler, fins de contrat, fins
de période d'essai. Les gestionnaires RH les reçoivent aussi dans le rappel quotidien par e-mail, 30 jours avant.

Ces données sont confidentielles : seuls les rôles « RH - Consultation » et « RH - Gestionnaire » y ont accès. La
paie n'est pas traitée. Les dossiers se saisissent dans l'application, ils ne sont pas dans le dépôt.

### Congés et absences

Tout salarié qui a un compte, le rôle « RH - Salarié » et un dossier relié à ce compte demande ses absences dans
RH > Congés et absences : congé annuel, permission exceptionnelle, maladie, maternité ou paternité, absence sans
solde. Circuit : accord du responsable (le responsable hiérarchique du dossier, sinon le responsable du service),
puis approbation des RH. Sans responsable, la demande va directement aux RH. Les RH peuvent aussi saisir une absence
pour un salarié (maladie, par exemple) et donner l'accord à la place du responsable.

- Les jours se comptent en **jours ouvrables**, du lundi au samedi. Les jours fériés ne sont pas déduits.
- **Solde de congés** : droits acquis par mois entier de service (2,2 jours par défaut, réglable dans
  l'administration : RH > Réglages RH), moins les congés approuvés. Pour reprendre l'existant, saisir sur le dossier
  le solde et la date à laquelle il a été arrêté ; sinon les droits sont comptés depuis l'embauche.
- Un congé qui dépasse le solde ne peut pas être approuvé. Deux absences d'un salarié ne se chevauchent pas.
- Le demandeur annule sa demande tant qu'elle n'est pas approuvée ; ensuite seules les RH l'annulent, avec un motif.
- Le **planning des absences** montre qui est absent sur une période. Chacun voit ses demandes et celles de son
  équipe ; les RH voient tout.
- Les demandes à traiter figurent dans le rappel quotidien par e-mail du responsable et des RH.

## HSE : événements et actions correctives

Tout salarié qui a un compte et le rôle « HSE - Déclarant » déclare un événement depuis son poste ou son téléphone :
accident du travail, presqu'accident, premiers soins, dégât matériel, atteinte à l'environnement, situation
dangereuse. Il indique la date, le site, le lieu, les faits, les mesures prises, le matériel en cause, et joint des
photos. Il peut corriger sa déclaration tant qu'elle n'est pas analysée.

Le responsable HSE (rôle « HSE - Responsable ») :

- enregistre l'**analyse des causes**, et corrige au besoin la gravité et les jours d'arrêt ;
- décide des **actions correctives**, chacune avec un responsable et une échéance ; le responsable de l'action la
  marque faite, le responsable HSE peut l'abandonner avec un motif ;
- **clôt** l'événement avec une conclusion, une fois toutes les actions faites ou abandonnées. Un événement clos
  peut être rouvert.

Chacun voit ses déclarations et les événements où une action lui est confiée ; le responsable HSE voit tout, avec
les chiffres de l'année (événements par type, accidents avec arrêt, jours d'arrêt, jours sans accident avec arrêt).
Le rappel quotidien par e-mail signale les déclarations à analyser et les actions en retard ou à faire sous 7 jours.

## HSE : visites de sécurité et équipements de protection

**Visites de sécurité** (HSE, Visites de sécurité). L'encadrement qui a le rôle « HSE - Visiteur » enregistre ses
visites depuis son téléphone : date, site, lieu ou activité, participants, bonnes pratiques et écarts constatés,
photos en pièces jointes. La visite reçoit un numéro `VS-AAAA-NNNN`. Le visiteur décide des actions correctives de
sa visite (responsable, échéance) ; elles suivent le même circuit que celles des événements et figurent dans les
mêmes rappels. Le responsable HSE voit toutes les visites, peut y ajouter des actions, et clôt la visite quand
toutes les actions sont faites ou abandonnées. Chacun voit les visites qu'il a menées et celles où une action lui
est confiée.

**Équipements de protection** (HSE, Équipements de protection), pour le responsable HSE : chaque remise à un salarié
(casque, chaussures, gants, gilet, lunettes, protections auditives, masque, harnais, tenue), avec le modèle ou la
taille, la quantité, la date de remise et, si besoin, la date de renouvellement. L'écran liste ce qui est à
renouveler dans les 30 jours ou en retard, et le rappel quotidien par e-mail le signale aussi. Une nouvelle remise
du même équipement au même salarié éteint l'alerte. Le responsable HSE choisit le salarié dans une liste réduite
(nom, matricule, site) : le dossier RH reste fermé.

Après la mise à jour : `manage.py migrate` crée le rôle « HSE - Visiteur » et complète les rôles HSE existants.
