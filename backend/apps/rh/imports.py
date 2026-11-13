"""Import du personnel depuis un classeur Excel.

Première feuille, première ligne = titres des colonnes, dans n'importe quel ordre. Obligatoires : nom, prénoms, et
le site pour un nouveau salarié. Facultatives : matricule, sexe, date de naissance, lieu de naissance, nationalité,
téléphone, e-mail, adresse, n° CNPS, service, fonction, catégorie, date d'embauche, solde de congés, solde arrêté au.
Un salarié déjà connu (même matricule, ou à défaut mêmes nom et prénoms) est mis à jour, les autres sont créés."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import transaction
from openpyxl import load_workbook

from apps.core.models import Service, Site
from apps.stock.imports import _cle, _nombre
from apps.technique.imports import _date

from .models import Salarie

COLONNES = {
    "matricule": ("matricule", "n matricule", "mle"),
    "nom": ("nom", "nom de famille"),
    "prenoms": ("prenoms", "prenom", "prenom(s)"),
    "sexe": ("sexe", "genre", "civilite"),
    "date_naissance": ("date de naissance", "naissance", "ne(e) le", "ne le"),
    "lieu_naissance": ("lieu de naissance",),
    "nationalite": ("nationalite",),
    "telephone": ("telephone", "tel", "contact", "portable"),
    "email": ("e-mail", "email", "mail", "courriel"),
    "adresse": ("adresse", "domicile"),
    "numero_cnps": ("n cnps", "cnps", "numero cnps", "no cnps"),
    "site": ("site", "site de rattachement", "agence", "lieu de travail"),
    "service": ("service", "departement", "direction"),
    "fonction": ("fonction", "poste", "emploi"),
    "categorie": ("categorie", "categorie professionnelle", "college"),
    "date_embauche": ("date d'embauche", "date embauche", "embauche", "date d'entree", "date entree"),
    "conges_solde_depart": ("solde de conges", "solde conges", "conges restants"),
    "conges_depuis": ("solde arrete au", "solde au"),
}
TEXTES = {"lieu_naissance": 100, "nationalite": 60, "telephone": 30, "adresse": 200, "numero_cnps": 30, "fonction": 100}
SEXES = {"m": "M", "h": "M", "homme": "M", "masculin": "M", "mr": "M", "monsieur": "M",
         "f": "F", "femme": "F", "feminin": "F", "mme": "F", "mlle": "F", "madame": "F"}
CATEGORIES = {"cadre": "CADRE", "maitrise": "MAITRISE", "agent de maitrise": "MAITRISE", "am": "MAITRISE",
              "employe": "EMPLOYE", "employee": "EMPLOYE", "ouvrier": "OUVRIER", "ouvriere": "OUVRIER"}
LIGNES_MAX = 2000
ATTENDUES = ("Colonne manquante. Colonnes attendues : nom, prénoms, site, puis au besoin matricule, sexe, date de naissance, "
             "lieu de naissance, nationalité, téléphone, e-mail, adresse, n° CNPS, service, fonction, catégorie, date d'embauche, "
             "solde de congés, solde arrêté au.")


def _jour(valeur, nom):
    try:
        return _date(valeur)
    except ValueError:
        raise ValueError(f"{nom} illisible (« {valeur} »)")


def importer(utilisateur, fichier, simuler=False) -> dict:
    """Lit le classeur et crée ou met à jour les dossiers. Avec `simuler`, rien n'est écrit : on obtient le compte
    rendu. S'il y a une seule ligne en erreur, rien n'est écrit non plus."""
    if not (utilisateur.has_perm("rh.add_salarie") and utilisateur.has_perm("rh.change_salarie")):
        raise PermissionDenied("Seul le gestionnaire RH peut importer le personnel.")
    try:
        feuille = load_workbook(fichier, data_only=True, read_only=True).worksheets[0]
    except Exception:
        raise ValidationError("Fichier illisible : il faut un classeur Excel (.xlsx).")
    lignes = feuille.iter_rows(values_only=True)
    try:
        titres = [_cle(str(c or "").replace("°", " ")) for c in next(lignes)]
    except StopIteration:
        raise ValidationError("Le classeur est vide.")
    col = {nom: next((titres.index(t) for t in variantes if t in titres), None) for nom, variantes in COLONNES.items()}
    if col["nom"] is None or col["prenoms"] is None:
        raise ValidationError(ATTENDUES)

    sites, services = {}, {}
    for s in Site.objects.all():
        sites[_cle(s.code)] = sites[_cle(s.nom)] = s
    for s in Service.objects.all():
        services[_cle(s.code)] = services[_cle(s.nom)] = s
    bilan = {"lues": 0, "crees": 0, "modifies": 0, "inchanges": 0, "erreurs": [], "simulation": simuler}
    vus = set()
    with transaction.atomic():
        for n, ligne in enumerate(lignes, start=2):
            def lire(nom):
                v = ligne[col[nom]] if col[nom] is not None and col[nom] < len(ligne) else None
                return v.strip() if isinstance(v, str) else v

            nom, prenoms = str(lire("nom") or "").strip(), str(lire("prenoms") or "").strip()
            matricule = str(lire("matricule") or "").strip()
            if not (nom or prenoms or matricule):
                continue
            bilan["lues"] += 1
            if bilan["lues"] > LIGNES_MAX:
                raise ValidationError(f"Trop de lignes : {LIGNES_MAX} au plus par fichier.")
            try:
                if not nom or not prenoms:
                    raise ValueError("nom ou prénoms manquant")
                if len(nom) > 80 or len(prenoms) > 120 or len(matricule) > 20:
                    raise ValueError("nom, prénoms ou matricule trop long")
                cle = ("m", matricule.lower()) if matricule else ("n", _cle(nom), _cle(prenoms))
                if cle in vus:
                    raise ValueError(f"{matricule or nom + ' ' + prenoms} figure deux fois")
                vus.add(cle)
                if matricule:
                    connus = list(Salarie.objects.filter(matricule__iexact=matricule))
                else:
                    connus = list(Salarie.objects.filter(nom__iexact=nom, prenoms__iexact=prenoms))
                    if len(connus) > 1:
                        raise ValueError("plusieurs salariés portent ce nom : indiquez le matricule")
                salarie = connus[0] if connus else None
                nouveau = salarie is None
                salarie = salarie or Salarie(matricule=matricule, cree_par=utilisateur)
                valeurs = {"nom": nom.upper(), "prenoms": prenoms}   # le dossier garde le nom en capitales
                for champ, longueur in TEXTES.items():
                    if lire(champ) not in (None, ""):
                        valeurs[champ] = str(lire(champ)).strip()[:longueur]
                for champ, table, libelle in (("sexe", SEXES, "sexe"), ("categorie", CATEGORIES, "catégorie"),
                                              ("site", sites, "site"), ("service", services, "service")):
                    if lire(champ) not in (None, ""):
                        if _cle(lire(champ)) not in table:
                            raise ValueError(f"{libelle} inconnu{'e' if libelle == 'catégorie' else ''} (« {lire(champ)} »)")
                        valeurs[champ] = table[_cle(lire(champ))]
                if lire("email") not in (None, ""):
                    try:
                        validate_email(str(lire("email")))
                    except ValidationError:
                        raise ValueError(f"e-mail invalide (« {lire('email')} »)")
                    valeurs["email"] = str(lire("email"))
                for champ, libelle in (("date_naissance", "date de naissance"), ("date_embauche", "date d'embauche"),
                                       ("conges_depuis", "date du solde de congés")):
                    jour = _jour(lire(champ), libelle)
                    if jour:
                        valeurs[champ] = jour
                solde = _nombre(lire("conges_solde_depart"), "solde de congés")
                if solde is not None:
                    if solde > 999:
                        raise ValueError("solde de congés invraisemblable")
                    valeurs["conges_solde_depart"] = solde.quantize(type(solde)("0.1"))
                if nouveau and "site" not in valeurs:
                    raise ValueError("site manquant pour un nouveau salarié")
                change = nouveau or any(getattr(salarie, c) != v for c, v in valeurs.items())
                if not change:
                    bilan["inchanges"] += 1
                    continue
                for c, v in valeurs.items():
                    setattr(salarie, c, v)
                try:
                    salarie.clean()
                except ValidationError as e:
                    raise ValueError(" ; ".join(e.messages).rstrip("."))
                salarie.modifie_par = utilisateur
                salarie.save()
                bilan["crees" if nouveau else "modifies"] += 1
            except ValueError as e:
                bilan["erreurs"].append(f"Ligne {n} : {e}.")
        if simuler or bilan["erreurs"]:
            transaction.set_rollback(True)
    bilan["erreurs"] = bilan["erreurs"][:50]
    bilan["ecrit"] = not simuler and not bilan["erreurs"]
    return bilan
