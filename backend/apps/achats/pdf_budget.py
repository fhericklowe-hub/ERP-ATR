"""Fiche PDF d'une demande liée au budget (DA frais généraux et sous-traitance, DI), avec les visas du circuit."""
from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table

from apps.core.devises import formate
from apps.core.models import Societe

from .pdf import BASE, GRAS, TITRE, _decor, date_fr

CENTRE = ParagraphStyle("centre", parent=BASE, alignment=TA_CENTER)
PETIT = ParagraphStyle("petit_centre", parent=CENTRE, fontSize=7, leading=9)
BANDEAU = ParagraphStyle("bandeau", parent=GRAS, textColor=colors.white)
GRIS = colors.HexColor("#1f2a5a")


def _section(titre, largeur):
    return Table([[Paragraph(titre.upper(), BANDEAU)]], colWidths=[largeur],
                 style=[("BACKGROUND", (0, 0), (-1, -1), GRIS), ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2)])


def _grille(lignes, largeur):
    """Tableau libellé / valeur sur deux colonnes doubles."""
    donnees = []
    for i in range(0, len(lignes), 2):
        paire = lignes[i:i + 2] + [("", "")] * (2 - len(lignes[i:i + 2]))
        donnees.append([c for libelle, valeur in paire
                        for c in (libelle, Paragraph(f"<b>{escape(str(valeur or '--'))}</b>" if libelle else "", BASE))])
    return Table(donnees, colWidths=[largeur * 0.17, largeur * 0.33, largeur * 0.17, largeur * 0.33],
                 style=[("FONT", (0, 0), (-1, -1), "Helvetica", 9), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)])


def pdf_demande_budget(d) -> bytes:
    societe = Societe.courante()
    tampon = BytesIO()
    S = d.Statut
    filigrane = {S.BROUILLON: "PROJET", S.REFUSEE: "REFUSÉE"}.get(d.statut)
    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=12 * mm,
                            bottomMargin=30 * mm, title=f"{d.numero}", author=societe.nom)
    largeur = doc.width
    oui_non = lambda v: "Oui" if v else "Non"  # noqa: E731

    logo = Image(societe.chemin_logo, width=32 * mm, height=22 * mm, kind="proportional")
    titre = [Paragraph(d.get_type_display().upper(), ParagraphStyle("t", parent=TITRE, alignment=TA_CENTER)),
             Paragraph(f"N° {d.numero} &nbsp;·&nbsp; {date_fr(d.date)} &nbsp;·&nbsp; {d.get_statut_display()}", CENTRE)]
    elements = [Table([[logo, titre]], colWidths=[largeur * 0.22, largeur * 0.78],
                      style=[("VALIGN", (0, 0), (-1, -1), "MIDDLE")]), Spacer(1, 4 * mm)]

    elements.append(_section("Demande", largeur))
    lignes = [
        ("Service demandeur", d.service.nom), ("Demandeur", f"{d.demandeur}" + (f", {d.demandeur.fonction}" if d.demandeur.fonction else "")),
        ("Site", d.site.nom), ("Fast-Track", oui_non(d.fast_track)),
        ("Activité", d.activite_libelle), ("Projet / client", d.projet.nom if d.projet else ""),
        ("Code analytique", d.projet.code_analytique if d.projet else ""), ("Intitulé", d.intitule),
    ]
    if d.est_investissement:
        lignes += [("Nature", d.get_nature_display()), ("Motif", d.get_motif_investissement_display())]
        if d.type == d.Type.INVEST_PRODUCTIF:
            lignes += [("N° de contrat", d.numero_contrat), ("Client", d.client.raison_sociale if d.client else ""),
                       ("Loyer mensuel", formate(d.loyer_mensuel) if d.loyer_mensuel else "")]
    elements.append(_grille(lignes, largeur))
    if d.description:
        elements.append(Paragraph(f"<b>Description :</b> {escape(d.description)}".replace("\n", "<br/>"), BASE))
    elements.append(Spacer(1, 3 * mm))

    elements.append(_section("Mise en concurrence", largeur))
    devis = [["", "Fournisseur", "N° de devis", "Date", "Montant"]]
    for x in d.devis.all():
        devis.append(["Retenu" if x.retenu else "", Paragraph(escape(x.fournisseur.raison_sociale), BASE), x.numero or "--",
                      date_fr(x.date), formate(x.montant)])
    if len(devis) == 1:
        devis.append(["", "Aucun devis enregistré", "", "", ""])
    styles = [("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
              ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black), ("ALIGN", (4, 0), (4, -1), "RIGHT"),
              ("VALIGN", (0, 0), (-1, -1), "TOP")]
    for i, x in enumerate(d.devis.all(), start=1):
        if x.retenu:
            styles.append(("FONT", (0, i), (-1, i), "Helvetica-Bold", 9))
    elements.append(Table(devis, colWidths=[largeur * 0.1, largeur * 0.4, largeur * 0.2, largeur * 0.13, largeur * 0.17], style=styles))
    criteres = [nom for nom, vrai in [("qualité", d.critere_qualite), ("délai", d.critere_delai), ("prix", d.critere_prix)] if vrai]
    if d.critere_autre:
        criteres.append(d.critere_autre)
    detail = [f"Critères de sélection : <b>{escape(', '.join(criteres)) or '--'}</b>"]
    if d.justification_devis:
        detail.append(f"Justification : {escape(d.justification_devis)}")
    if d.acheteur_id:
        detail.append(f"Acheteur : {d.acheteur}")
    elements.append(Paragraph(" &nbsp;·&nbsp; ".join(detail), BASE))
    elements.append(Spacer(1, 3 * mm))

    elements.append(_section("Imputation et budget", largeur))
    lignes = [("Service imputé", d.service_impute.nom if d.service_impute else ""),
              ("Compte comptable", str(d.compte) if d.compte else ""),
              ("Article NG", d.compte.article_ng if d.compte else ""),
              ("Montant", f"{formate(d.montant)} {societe.devise}" if d.montant else "")]
    if d.est_investissement:
        lignes.append(("Amortissement", f"{d.duree_amortissement} mois" if d.duree_amortissement else ""))
    elements.append(_grille(lignes, largeur))
    situation = d.situation_budget()
    if situation:
        elements.append(Paragraph(f"Ligne budgétaire : <b>{escape(str(d.ligne_budgetaire))}</b>", BASE))
        elements.append(Table(
            [["Budget", "Déjà engagé", "Disponible", "À engager", "Solde"],
             [formate(situation[c]) for c in ["budget", "engage", "disponible", "a_engager", "solde"]]],
            colWidths=[largeur * 0.2] * 5,
            style=[("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
                   ("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                   ("TEXTCOLOR", (4, 1), (4, 1), colors.red if situation["solde"] < 0 else colors.black)],
        ))
    else:
        motif = f" Motif : {escape(d.motif_hors_budget)}" if d.motif_hors_budget else ""
        elements.append(Paragraph("<b>Hors budget.</b>" + motif if not d.prevu_budget else "Ligne budgétaire non renseignée.", BASE))
    motifs = d.motifs_dg()
    if motifs:
        elements.append(Paragraph(f"Validation de la direction générale requise : {', '.join(motifs)}.", BASE))
    elements.append(Spacer(1, 5 * mm))

    # Visas : la signature de chaque valideur s'imprime dès qu'il a validé dans l'application.
    signatures = d.signatures()
    cadres = []
    for libelle, e in signatures:
        cadre = [Paragraph(f"<b>{libelle}</b>", PETIT)]
        if e:
            if e.auteur.signature:
                image = Image(e.auteur.signature.path, width=28 * mm, height=13 * mm, kind="proportional")
                image.hAlign = "CENTER"
                cadre.append(image)
            else:
                cadre.append(Spacer(1, 13 * mm))
            moment = timezone.localtime(e.date)
            cadre.append(Paragraph(f"{e.auteur}<br/>{date_fr(moment)} à {moment:%H:%M}", PETIT))
        else:
            cadre += [Spacer(1, 13 * mm), Paragraph("En attente", PETIT)]
        cadres.append(cadre)
    elements.append(Table([cadres], colWidths=[largeur / len(cadres)] * len(cadres), rowHeights=[28 * mm],
                          style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))

    decor = _decor(societe, filigrane)
    doc.build(elements, onFirstPage=decor, onLaterPages=decor)
    return tampon.getvalue()
