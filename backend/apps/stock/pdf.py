"""Bon de sortie en PDF, à faire signer par le magasinier et par la personne qui reçoit les pièces."""
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table

from apps.achats.pdf import BASE, TITRE, _decor, date_fr, quantite
from apps.core.models import Societe


def pdf_bon_sortie(bon) -> bytes:
    societe = Societe.courante()
    tampon = BytesIO()
    filigrane = "ANNULÉ" if bon.statut == bon.Statut.ANNULE else None
    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=15 * mm,
                            bottomMargin=30 * mm, title=f"Bon de sortie {bon.numero}", author=societe.nom)
    largeur = doc.width
    logo = Image(societe.chemin_logo, width=42 * mm, height=30 * mm, kind="proportional")
    logo.hAlign = "LEFT"
    droite = ParagraphStyle("d", parent=TITRE, alignment=TA_RIGHT)
    elements = [
        Table([[logo, [Paragraph(f"BON DE SORTIE N° {bon.numero}", droite),
                       Paragraph(f"Date : {date_fr(bon.date)}", droite),
                       Paragraph(f"Magasin : {bon.magasin.nom}", droite)]]],
              colWidths=[largeur * 0.45, largeur * 0.55], style=[("VALIGN", (0, 0), (-1, -1), "TOP")]),
        Table([[""]], colWidths=[largeur], rowHeights=[3 * mm], style=[("LINEBELOW", (0, 0), (-1, -1), 0.8, colors.black)]),
        Spacer(1, 4 * mm),
    ]
    infos = [
        ["N° d'OR", Paragraph(f"<b>{bon.numero_or}</b>", BASE), "Matériel", Paragraph(bon.materiel or "--", BASE)],
        ["Remis à", str(bon.remis_a).upper(), "Service", bon.service.nom if bon.service_id else "--"],
        ["Magasinier", str(bon.magasinier).upper(), "", ""],
    ]
    elements.append(Table(infos, colWidths=[largeur * 0.15, largeur * 0.35, largeur * 0.13, largeur * 0.37],
                          style=[("FONT", (0, 0), (-1, -1), "Helvetica", 9), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 1)]))
    elements.append(Spacer(1, 6 * mm))

    donnees = [["Code", "Désignation", "Quantité", "Unité"]]
    for l in bon.lignes.select_related("article__unite"):
        donnees.append([l.article.code, Paragraph(l.article.designation, BASE), quantite(l.quantite), l.article.unite.code])
    elements.append(Table(
        donnees, repeatRows=1, colWidths=[largeur * 0.2, largeur * 0.55, largeur * 0.13, largeur * 0.12],
        style=[("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9), ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
               ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.black), ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
               ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.black), ("ALIGN", (2, 0), (2, -1), "RIGHT"),
               ("VALIGN", (0, 0), (-1, -1), "TOP")],
    ))
    if bon.observations:
        elements.append(Spacer(1, 4 * mm))
        elements.append(Paragraph(f"<b>Observations :</b> {bon.observations}".replace("\n", "<br/>"), BASE))
    elements.append(Spacer(1, 8 * mm))

    petit = ParagraphStyle("petit", parent=BASE, fontSize=8, leading=10)
    if bon.statut == bon.Statut.ANNULE:
        visa = f"Bon annulé : {bon.motif_annulation}"
    else:
        visa = f"Sortie enregistrée par {bon.magasinier} le {date_fr(timezone.localtime(bon.cree_le))}"
    centre = ParagraphStyle("s", parent=BASE, alignment=TA_CENTER)
    elements.append(Table(
        [[Paragraph(visa, petit), Paragraph("<b>Visa du magasinier</b>", centre), Paragraph("<b>Visa du receveur</b>", centre)]],
        colWidths=[largeur * 0.4, largeur * 0.3, largeur * 0.3], rowHeights=[25 * mm],
        style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (1, 0), (1, 0), 0.5, colors.grey),
               ("BOX", (2, 0), (2, 0), 0.5, colors.grey)],
    ))
    decor = _decor(societe, filigrane)
    doc.build(elements, onFirstPage=decor, onLaterPages=decor)
    return tampon.getvalue()
