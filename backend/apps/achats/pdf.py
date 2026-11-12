"""Mise en page PDF du bon de commande, calquée sur le document actuel."""
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.core.models import Societe

BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=9, leading=11)
GRAS = ParagraphStyle("gras", parent=BASE, fontName="Helvetica-Bold")
TITRE = ParagraphStyle("titre", parent=GRAS, fontSize=11, leading=14)
DROITE = ParagraphStyle("droite", parent=BASE, alignment=TA_RIGHT)
PIED = ParagraphStyle("pied", parent=BASE, fontSize=7, leading=9, alignment=TA_CENTER)


def nombre(n) -> str:
    """Montant entier avec espace comme séparateur de milliers."""
    return f"{int(round(n)):,}".replace(",", " ")


def quantite(q) -> str:
    return f"{q.normalize():f}".replace(".", ",")


def date_fr(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "--"


def pdf_bon_commande(bon) -> bytes:
    societe = Societe.courante()
    totaux = bon.totaux()
    tampon = BytesIO()

    def decor(canvas, doc):
        canvas.saveState()
        if not bon.definitif:  # pas encore ses deux validations : ne peut pas passer pour un bon définitif
            canvas.setFont("Helvetica-Bold", 70)
            canvas.setFillColor(colors.Color(0.85, 0.1, 0.1, alpha=0.18))
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(45)
            libelle = "ANNULÉ" if bon.statut == bon.Statut.ANNULE else "PROJET"
            canvas.drawCentredString(0, 0, libelle)
            canvas.restoreState()
            canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#c9a227"))
        canvas.line(20 * mm, 24 * mm, A4[0] - 20 * mm, 24 * mm)
        lignes = [
            f"<b>{societe.nom}</b>",
            societe.forme_capital,
            f"Siège social : {societe.adresse}" if societe.adresse else "",
            " / ".join(filter(None, [f"RCCM {societe.rccm}" if societe.rccm else "",
                                     f"CC N°{societe.compte_contribuable}" if societe.compte_contribuable else ""])),
            " - ".join(filter(None, [f"Tél : {societe.telephone}" if societe.telephone else "",
                                     f"Email : {societe.email}" if societe.email else ""])),
            societe.banque,
        ]
        p = Paragraph("<br/>".join(l for l in lignes if l), PIED)
        _, h = p.wrap(A4[0] - 40 * mm, 20 * mm)
        p.drawOn(canvas, 20 * mm, 22 * mm - h)
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(A4[0] - 20 * mm, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=15 * mm,
                            bottomMargin=30 * mm, title=f"Bon de commande {bon.numero}", author=societe.nom)
    largeur = doc.width
    f = bon.fournisseur
    elements = []

    # En-tête : société à gauche, fournisseur à droite
    if societe.logo:
        gauche = [Image(societe.logo.path, width=35 * mm, height=22 * mm, kind="proportional")]
    else:
        gauche = [Paragraph(societe.nom, TITRE)]
    fiscal = [f"N° CC : <b>{societe.compte_contribuable}</b>" if societe.compte_contribuable else "",
              f"Régime d'imposition : <b>{societe.regime_imposition}</b>" if societe.regime_imposition else "",
              f"Centre des impôts : <b>{societe.centre_impots}</b>" if societe.centre_impots else ""]
    gauche.append(Paragraph("<br/>".join(x for x in fiscal if x), ParagraphStyle("f", parent=BASE, fontSize=7, leading=9)))
    droite = [Paragraph(f.raison_sociale, TITRE),
              Paragraph("<br/>".join(x for x in [f.adresse.replace("\n", "<br/>"), f.ville,
                                                  f"Téléphone : {f.telephone}" if f.telephone else ""] if x), BASE)]
    elements.append(Table([[gauche, droite]], colWidths=[largeur * 0.5, largeur * 0.5],
                          style=[("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(Spacer(1, 8 * mm))

    elements.append(Table(
        [[Paragraph(f"BON DE COMMANDE N° {bon.numero}", TITRE), Paragraph(f"N° fournisseur : {f.code}", TITRE),
          Paragraph(f"Date : {date_fr(bon.date)}", ParagraphStyle("d", parent=TITRE, alignment=TA_RIGHT))]],
        colWidths=[largeur * 0.47, largeur * 0.28, largeur * 0.25],
    ))
    sous = [f"Demande d'achat : {bon.demande.numero}"]
    if bon.reference_fournisseur:
        sous.append(f"N° commande fournisseur : {bon.reference_fournisseur}")
    if bon.ancien_numero:
        sous.append(f"N° ancien logiciel : {bon.ancien_numero}")
    elements.append(Paragraph(" &nbsp;·&nbsp; ".join(sous), BASE))
    elements.append(Table([[""]], colWidths=[largeur], rowHeights=[2 * mm],
                          style=[("LINEBELOW", (0, 0), (-1, -1), 0.8, colors.black)]))
    elements.append(Spacer(1, 3 * mm))

    infos = [
        ["Succursale", bon.site.nom, "Délai", date_fr(bon.date_livraison)],
        ["Service", f"{bon.service.code} - {bon.service.nom}", "Transport", bon.transport or "--"],
        ["Opérateur", str(bon.acheteur).upper(), "Référence", Paragraph(f"<b>{bon.objet or '--'}</b>", BASE)],
    ]
    elements.append(Table(infos, colWidths=[largeur * 0.15, largeur * 0.37, largeur * 0.13, largeur * 0.35],
                          style=[("FONT", (0, 0), (-1, -1), "Helvetica", 9), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 1)]))
    if bon.adresse_livraison:
        elements.append(Spacer(1, 3 * mm))
        elements.append(Paragraph("<u><b>Adresse livraison</b></u>", BASE))
        elements.append(Paragraph(bon.adresse_livraison.replace("\n", "<br/>"), BASE))
    elements.append(Spacer(1, 6 * mm))

    # Lignes
    donnees = [["Quantité", "Référence / Désignation", "Prix Unit HT", "Remise", "P.U. Net", "Montant HT"]]
    for l in bon.lignes.all():
        libelle = f"{l.reference} &nbsp; {l.designation}" if l.reference else l.designation
        donnees.append([quantite(l.quantite), Paragraph(libelle, BASE), nombre(l.prix_unitaire),
                        f"{quantite(l.remise)} %" if l.remise else "", nombre(l.prix_net), nombre(l.montant_ht)])
    elements.append(Table(
        donnees, repeatRows=1,
        colWidths=[largeur * 0.1, largeur * 0.42, largeur * 0.14, largeur * 0.1, largeur * 0.12, largeur * 0.12],
        style=[("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9), ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
               ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.black), ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
               ("ALIGN", (2, 0), (-1, -1), "RIGHT"), ("ALIGN", (0, 0), (0, -1), "CENTER"),
               ("VALIGN", (0, 0), (-1, -1), "TOP")],
    ))
    elements.append(Spacer(1, 10 * mm))

    # Pied : TVA et totaux
    tva = [["TVA %", "Base HT", "Montant TVA", "Montant TTC"]]
    for v in totaux["ventilation"]:
        tva.append([quantite(v["taux"]), nombre(v["base_ht"]), nombre(v["tva"]), nombre(v["ttc"])])
    bloc_tva = Table(tva, colWidths=[largeur * 0.1, largeur * 0.15, largeur * 0.15, largeur * 0.15],
                     style=[("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
                            ("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.black)])
    tot = [["Total HT", nombre(totaux["total_ht"])], ["Total TVA", nombre(totaux["total_tva"])],
           ["Total TTC", nombre(totaux["total_ttc"])], ["Devise", societe.devise]]
    bloc_tot = Table(tot, colWidths=[largeur * 0.2, largeur * 0.2],
                     style=[("FONT", (0, 0), (-1, -1), "Helvetica-Bold", 10), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                            ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.black)])
    elements.append(Table([[bloc_tva, bloc_tot]], colWidths=[largeur * 0.6, largeur * 0.4],
                          style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    reglement = bon.get_mode_reglement_display().upper()
    elements.append(Paragraph(f"<b>À échéance : {bon.echeance}</b> par {reglement}" if bon.echeance
                              else f"Règlement par {reglement}", BASE))
    elements.append(Table([[Paragraph(totaux["en_lettres"], BASE)]], colWidths=[largeur],
                          style=[("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.black),
                                 ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black)]))
    elements.append(Spacer(1, 8 * mm))

    # Validations enregistrées dans le système, puis emplacement de la signature manuscrite
    validations = [e for e in bon.evenements.all() if e.action == "VALIDATION"]
    visas = [f"Validé par {e.auteur} le {date_fr(timezone.localtime(e.date))}" for e in validations[-2:]] if bon.definitif else []
    elements.append(Table(
        [[Paragraph("<br/>".join(visas) or "En attente de validation", ParagraphStyle("v", parent=BASE, fontSize=8)),
          Paragraph("<b>Signature et cachet</b>", ParagraphStyle("s", parent=BASE, alignment=TA_CENTER))]],
        colWidths=[largeur * 0.55, largeur * 0.45], rowHeights=[28 * mm],
        style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (1, 0), (1, 0), 0.5, colors.grey)],
    ))

    doc.build(elements, onFirstPage=decor, onLaterPages=decor)
    return tampon.getvalue()
