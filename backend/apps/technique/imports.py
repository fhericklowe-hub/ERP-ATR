"""Import du parc de matériels depuis un classeur Excel.

Deux formes de classeur :

1. Le classeur de l'exploitation, avec un onglet par site et par activité (ABJ-Transport, ABJ-Manutention, ABJ-Levage,
   SP-…, FKE-…) : le site et l'activité se déduisent du nom de l'onglet, les titres sont cherchés dans les premières lignes,
   les autres onglets (synthèse, hors exploitation, exclus, corrections, inventaire des dollies) sont laissés de côté.
2. Un classeur simple : première feuille, première ligne = titres des colonnes, dans n'importe quel ordre. Obligatoires : n° de parc,
désignation, type, site. Facultatives : marque, modèle, n° de série, immatriculation, année, capacité, activité,
compteur heures, compteur km, mise en service. Un n° de parc déjà connu est mis à jour, les autres sont créés."""
import datetime
import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from openpyxl import load_workbook

from apps.achats.choix import Activite
from apps.core.models import Site
from apps.referentiels.models import Emplacement, Tiers
from apps.stock.imports import _cle, _nombre

from .models import Materiel

COLONNES = {
    "code": ("n de parc", "no de parc", "numero de parc", "n parc", "code", "parc"),
    "designation": ("designation", "libelle", "materiel", "engin"),
    "type": ("type", "categorie", "famille"),
    "site": ("site", "site de rattachement", "agence"),
    "marque": ("marque",),
    "modele": ("modele",),
    "numero_serie": ("n de serie", "no de serie", "numero de serie", "serie", "chassis", "n de chassis"),
    "immatriculation": ("immatriculation", "immat", "plaque"),
    "annee": ("annee",),
    "capacite": ("capacite", "tonnage"),
    "activite": ("activite",),
    "compteur_heures": ("compteur heures", "heures", "compteur h", "compteur (heures)"),
    "compteur_km": ("compteur km", "km", "kilometrage", "compteur (km)"),
    "date_mise_en_service": ("mise en service", "date de mise en service"),
}
TEXTES = {"designation": 150, "marque": 60, "modele": 60, "numero_serie": 60, "immatriculation": 30, "capacite": 40}
# Mots usuels acceptés en plus des libellés exacts des types.
SYNONYMES = {"chariot": "CHARIOT", "chariot elevateur": "CHARIOT", "grue": "GRUE", "grue mobile": "GRUE", "nacelle": "NACELLE",
             "camion": "CAMION", "porteur": "CAMION", "tracteur": "TRACTEUR", "tracteur routier": "TRACTEUR",
             "remorque": "REMORQUE", "semi-remorque": "REMORQUE", "semi remorque": "REMORQUE", "porte-char": "REMORQUE",
             "vehicule": "VEHICULE", "vehicule leger": "VEHICULE", "voiture": "VEHICULE", "pick-up": "VEHICULE",
             "groupe": "GROUPE", "groupe electrogene": "GROUPE", "compresseur": "GROUPE", "autre": "AUTRE"}
LIGNES_MAX = 2000

# ----- classeur de l'exploitation (un onglet par site et par activité)
FEUILLE = re.compile(r"^(abj|sp|fke)\s*-\s*(transport|manutention|levage)$")
SITES_DES_ONGLETS = {"abj": ("siege", "abidjan"), "sp": ("san pedro", "sanpedro"), "fke": ("ferke",)}
ACTIVITES_DES_ONGLETS = {"transport": "TRANSPORT", "manutention": "MANUTENTION", "levage": "LEVAGE"}
NATURES = {"RMQ": "REMORQUE", "DOL": "REMORQUE", "TRAC": "TRACTEUR", "VHL": "VEHICULE", "CHTH": "CHARIOT", "CHEL": "CHARIOT",
           "CHGT": "CHARIOT", "CHTL": "CHARIOT", "MAG": "AUTRE", "CHRG": "AUTRE", "PELL": "AUTRE", "ZZCH": "AUTRE", "COMP": "GROUPE", "GE": "GROUPE",
           "NACL": "NACELLE", "GRU": "GRUE"}
ETATS = {"en mission": "EXPLOITE", "en exploitation": "EXPLOITE", "materiel loue exterieurement": "EXPLOITE",
         "disponible": "DISPONIBLE", "disponible commercialement": "DISPONIBLE", "en reserve": "DISPONIBLE",
         "en reserve // brassivoire": "DISPONIBLE", "nouvelle acquisition": "DISPONIBLE", "accessoire": "DISPONIBLE",
         "en panne": "EN_PANNE", "hs": "EN_PANNE", "hors service": "EN_PANNE", "hors service /vnc": "EN_PANNE",
         "accidente": "EN_PANNE", "en attente reparation": "EN_PANNE", "en attente de pieces": "EN_PANNE",
         "hors exploitation": "EN_PANNE", "hors exploitation attente validation devis": "EN_PANNE",
         "en maintenance": "REPARATION", "en reparation": "REPARATION"}
TITRES_CLASSEUR = {
    "code": "n parc", "numero_ie": "n materiel", "immatriculation": "immatriculation / identite", "numero_serie": "n serie",
    "nature": "nature", "designation": "designation", "marque": "marque", "modele": "modele", "tonnage": "tonnage",
    "capacite": "capacite", "annee": "annee / 1ere mec", "client": "client", "statut": "statut", "observations": "observations",
    "localisation": "localisation",
}


def _date(valeur):
    if valeur in (None, ""):
        return None
    if isinstance(valeur, datetime.datetime):
        return valeur.date()
    if isinstance(valeur, datetime.date):
        return valeur
    for forme in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(str(valeur).strip(), forme).date()
        except ValueError:
            pass
    raise ValueError(f"date de mise en service illisible (« {valeur} »)")


def importer(utilisateur, fichier, simuler=False) -> dict:
    """Lit le classeur et crée ou met à jour les matériels. Avec `simuler`, rien n'est écrit : on obtient le compte
    rendu. S'il y a une seule ligne en erreur, rien n'est écrit non plus."""
    if not (utilisateur.has_perm("technique.add_materiel") and utilisateur.has_perm("technique.change_materiel")):
        raise PermissionDenied("Seul le chef d'atelier peut importer le parc.")
    try:
        classeur = load_workbook(fichier, data_only=True, read_only=True)
        feuille = classeur.worksheets[0]
    except Exception:
        raise ValidationError("Fichier illisible : il faut un classeur Excel (.xlsx).")
    if any(FEUILLE.match(_cle(f.title)) for f in classeur.worksheets):
        return _importer_classeur(utilisateur, classeur, simuler)
    lignes = feuille.iter_rows(values_only=True)
    try:
        titres = [_cle(str(c or "").replace("°", " ")) for c in next(lignes)]
    except StopIteration:
        raise ValidationError("Le classeur est vide.")
    col = {nom: next((titres.index(t) for t in variantes if t in titres), None) for nom, variantes in COLONNES.items()}
    if col["code"] is None or col["designation"] is None:
        raise ValidationError("Colonne manquante. Colonnes attendues : n° de parc, désignation, type, site, puis au besoin "
                              "marque, modèle, n° de série, immatriculation, année, capacité, activité, compteur heures, "
                              "compteur km, mise en service.")

    types = {**SYNONYMES, **{_cle(v): v for v, _ in Materiel.Type.choices}, **{_cle(l): v for v, l in Materiel.Type.choices}}
    activites = {**{_cle(v): v for v, _ in Activite.choices}, **{_cle(l): v for v, l in Activite.choices}}
    sites = {}
    for s in Site.objects.all():
        sites[_cle(s.code)] = sites[_cle(s.nom)] = s
    bilan = {"lues": 0, "crees": 0, "modifies": 0, "inchanges": 0, "erreurs": [], "simulation": simuler}
    vus = set()
    with transaction.atomic():
        for n, ligne in enumerate(lignes, start=2):
            def lire(nom):
                v = ligne[col[nom]] if col[nom] is not None and col[nom] < len(ligne) else None
                return v.strip() if isinstance(v, str) else v

            code = str(lire("code") or "").strip()
            if not code and not lire("designation"):
                continue
            bilan["lues"] += 1
            if bilan["lues"] > LIGNES_MAX:
                raise ValidationError(f"Trop de lignes : {LIGNES_MAX} au plus par fichier.")
            try:
                if not code:
                    raise ValueError("n° de parc manquant")
                if len(code) > 30:
                    raise ValueError("n° de parc trop long (30 caractères au plus)")
                if code.lower() in vus:
                    raise ValueError(f"le n° de parc {code} figure deux fois")
                vus.add(code.lower())
                materiel = Materiel.objects.filter(code__iexact=code).first()
                nouveau = materiel is None
                materiel = materiel or Materiel(code=code, cree_par=utilisateur)
                valeurs = {}
                for champ, longueur in TEXTES.items():
                    if lire(champ) not in (None, ""):
                        valeurs[champ] = str(lire(champ))[:longueur]
                if lire("type") not in (None, ""):
                    if _cle(lire("type")) not in types:
                        raise ValueError(f"type inconnu (« {lire('type')} »)")
                    valeurs["type"] = types[_cle(lire("type"))]
                if lire("site") not in (None, ""):
                    if _cle(lire("site")) not in sites:
                        raise ValueError(f"site inconnu (« {lire('site')} »)")
                    valeurs["site"] = sites[_cle(lire("site"))]
                if lire("activite") not in (None, ""):
                    if _cle(lire("activite")) not in activites:
                        raise ValueError(f"activité inconnue (« {lire('activite')} »)")
                    valeurs["activite"] = activites[_cle(lire("activite"))]
                annee = _nombre(lire("annee"), "année")
                if annee is not None:
                    if not 1950 <= annee <= 2100 or annee != int(annee):
                        raise ValueError(f"année invraisemblable (« {lire('annee')} »)")
                    valeurs["annee"] = int(annee)
                heures, km = _nombre(lire("compteur_heures"), "compteur heures"), _nombre(lire("compteur_km"), "compteur km")
                if heures is not None:
                    valeurs["compteur_heures"] = heures.quantize(type(heures)("0.1"))
                if km is not None:
                    valeurs["compteur_km"] = int(km)
                mise = _date(lire("date_mise_en_service"))
                if mise:
                    valeurs["date_mise_en_service"] = mise
                if nouveau:
                    manque = [nom for nom in ("designation", "type", "site") if nom not in valeurs]
                    if manque:
                        raise ValueError(", ".join(manque).replace("designation", "désignation") + " manquant pour un matériel nouveau")
                change = nouveau or any(getattr(materiel, c) != v for c, v in valeurs.items())
                if not change:
                    bilan["inchanges"] += 1
                    continue
                for c, v in valeurs.items():
                    setattr(materiel, c, v)
                materiel.modifie_par = utilisateur
                materiel.save()
                bilan["crees" if nouveau else "modifies"] += 1
            except ValueError as e:
                bilan["erreurs"].append(f"Ligne {n} : {e}.")
        if simuler or bilan["erreurs"]:
            transaction.set_rollback(True)
    bilan["erreurs"] = bilan["erreurs"][:50]
    bilan["ecrit"] = not simuler and not bilan["erreurs"]
    return bilan


def _t(cellule) -> str:
    return _cle(re.sub(r"\([^)]*\)", " ", str(cellule or "").replace("°", " ")))


def _capacite(tonnage, capacite, levage) -> str:
    morceaux = []
    for v, est_capacite in ((tonnage, False), (capacite, True)):
        if v in (None, "") or (est_capacite and not levage):
            continue
        texte = (f"{v:g}" if isinstance(v, float) else str(v)).strip()
        morceaux.append(f"{texte} t" if re.fullmatch(r"[\d.,]+", texte) else texte)
    return " · ".join(morceaux)[:40]


def _importer_classeur(utilisateur, classeur, simuler) -> dict:
    """Classeur de l'exploitation : un matériel par ligne des onglets « site-activité »."""
    sites = {}
    for s in Site.objects.all():
        sites[_cle(s.code)] = sites[_cle(s.nom)] = s
    clients = {_cle(t.raison_sociale): t for t in Tiers.objects.filter(est_client=True)}
    bilan = {"lues": 0, "crees": 0, "modifies": 0, "inchanges": 0, "erreurs": [], "avertissements": [], "simulation": simuler,
             "feuilles": [], "feuilles_ignorees": []}
    vus, codes_ie, statuts_inconnus, clients_inconnus, sans_code = set(), set(), {}, {}, 0
    with transaction.atomic():
        for feuille in classeur.worksheets:
            onglet = FEUILLE.match(_cle(feuille.title))
            if not onglet:
                bilan["feuilles_ignorees"].append(feuille.title)
                continue
            prefixe, activite = onglet.group(1), ACTIVITES_DES_ONGLETS[onglet.group(2)]
            site = next((sites[c] for c in SITES_DES_ONGLETS[prefixe] if c in sites), None)
            if site is None:
                bilan["erreurs"].append(f"Onglet {feuille.title} : aucun site de l'entreprise ne correspond "
                                        f"(« {SITES_DES_ONGLETS[prefixe][0]} »). Créez-le dans l'administration.")
                continue
            lignes = feuille.iter_rows(values_only=True)
            col, depart = None, 0
            for depart, ligne in enumerate(lignes, start=1):
                titres = [_t(c) for c in ligne]
                if "n parc" in titres and "nature" in titres:
                    col = {nom: titres.index(t) if t in titres else None for nom, t in TITRES_CLASSEUR.items()}
                    break
                if depart >= 10:
                    break
            if col is None:
                bilan["erreurs"].append(f"Onglet {feuille.title} : titres introuvables (il faut au moins « N° parc » et « Nature »).")
                continue
            lues_onglet = 0
            for n, ligne in enumerate(lignes, start=depart + 1):
                def lire(nom):
                    v = ligne[col[nom]] if col[nom] is not None and col[nom] < len(ligne) else None
                    return v.strip() if isinstance(v, str) else v

                code, numero_ie = str(lire("code") or "").strip(), str(lire("numero_ie") or "").strip()
                if not code and not numero_ie and not lire("designation"):
                    continue
                lues_onglet += 1
                bilan["lues"] += 1
                if bilan["lues"] > LIGNES_MAX:
                    raise ValidationError(f"Trop de lignes : {LIGNES_MAX} au plus par fichier.")
                lieu = f"{feuille.title}, ligne {n}"
                try:
                    if not code:
                        if not numero_ie:
                            raise ValueError("ni n° de parc ni n° de matériel")
                        code, sans_code = f"M{numero_ie}", sans_code + 1
                    if len(code) > 30:
                        raise ValueError("n° de parc trop long (30 caractères au plus)")
                    if code.lower() in vus:
                        raise ValueError(f"le n° de parc {code} figure deux fois")
                    vus.add(code.lower())
                    nature = str(lire("nature") or "").strip().upper()
                    if nature not in NATURES:
                        raise ValueError(f"nature inconnue (« {lire('nature') or ''} »)")
                    if not lire("designation"):
                        raise ValueError("désignation manquante")
                    valeurs = {"type": NATURES[nature], "site": site, "activite": activite, "numero_ie": numero_ie[:20],
                               "designation": str(lire("designation"))[:150]}
                    for champ, longueur in (("marque", 60), ("modele", 60), ("numero_serie", 60), ("immatriculation", 30)):
                        if lire(champ) not in (None, ""):
                            valeurs[champ] = str(lire(champ))[:longueur]
                    capacite = _capacite(lire("tonnage"), lire("capacite"), activite == "LEVAGE")
                    if capacite:
                        valeurs["capacite"] = capacite
                    mec = lire("annee")
                    if isinstance(mec, datetime.datetime):
                        mec = mec.date()
                    if isinstance(mec, datetime.date):
                        valeurs["date_mise_en_service"], mec = mec, mec.year
                    if isinstance(mec, (int, float)) and 1950 <= mec <= 2100:
                        valeurs["annee"] = int(mec)
                    notes = [str(lire("observations"))] if lire("observations") else []
                    if lire("localisation"):
                        notes.append(f"Localisation : {lire('localisation')}")
                    statut = _cle(lire("statut"))
                    if statut in ETATS:
                        valeurs["etat"] = ETATS[statut]
                    elif statut:
                        statuts_inconnus[statut] = lire("statut")
                        notes.append(f"Statut (fichier) : {lire('statut')}")
                    client = _cle(lire("client"))
                    if client in clients:
                        valeurs["emplacement"] = (Emplacement.objects.filter(type="CLIENT", client=clients[client]).first()
                                                  or Emplacement.objects.create(type="CLIENT", client=clients[client],
                                                                                nom=clients[client].raison_sociale[:150]))
                    elif client and not re.match(r"(base )?atr\b", client):
                        clients_inconnus[client] = str(lire("client"))
                        notes.append(f"Client (fichier) : {lire('client')}")
                    if notes:
                        valeurs["observations"] = " · ".join(notes)
                    materiel = Materiel.objects.filter(code__iexact=code).first()
                    nouveau = materiel is None
                    materiel = materiel or Materiel(code=code, cree_par=utilisateur)
                    if not nouveau and not numero_ie:
                        valeurs.pop("numero_ie")
                    if not (nouveau or any(getattr(materiel, c) != v for c, v in valeurs.items())):
                        bilan["inchanges"] += 1
                        continue
                    for c, v in valeurs.items():
                        setattr(materiel, c, v)
                    materiel.modifie_par = utilisateur
                    materiel.save()
                    bilan["crees" if nouveau else "modifies"] += 1
                except ValueError as e:
                    bilan["erreurs"].append(f"{lieu} : {e}.")
            bilan["feuilles"].append({"nom": feuille.title, "lues": lues_onglet})
        if sans_code:
            bilan["avertissements"].append(f"{sans_code} matériel(s) sans n° de parc : le code « M » suivi du n° de matériel "
                                           "leur est donné, à remplacer plus tard par le vrai n° de parc.")
        if statuts_inconnus:
            bilan["avertissements"].append("Statut non reconnu (état laissé à « disponible », statut noté dans les observations) : "
                                           + ", ".join(sorted(map(str, statuts_inconnus.values()))) + ".")
        if clients_inconnus:
            bilan["avertissements"].append(f"{len(clients_inconnus)} client(s) absents de l'annuaire (noms notés dans les "
                                           "observations, matériel non placé chez eux) : " + ", ".join(sorted(clients_inconnus.values())[:15])
                                           + (" …" if len(clients_inconnus) > 15 else "") + ".")
        if not bilan["feuilles"] and not bilan["erreurs"]:
            bilan["erreurs"].append("Aucun onglet exploitable.")
        if simuler or bilan["erreurs"]:
            transaction.set_rollback(True)
    bilan["erreurs"] = bilan["erreurs"][:50]
    bilan["ecrit"] = not simuler and not bilan["erreurs"]
    return bilan
