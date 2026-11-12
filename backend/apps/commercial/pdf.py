"""PDF du devis de location, calqué sur le document actuel de l'entreprise (devis puis « commande client »)."""
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.achats.pdf import BASE, DROITE, GRAS, TITRE, _entete, date_fr, quantite
from apps.core.devises import formate
from apps.core.models import Societe

from .models import ReglageCommercial

PETIT = ParagraphStyle("petit", parent=BASE, fontSize=6, leading=7.2)
CENTRE = ParagraphStyle("centre", parent=BASE, alignment=TA_CENTER)


def _decor(societe, extrait, filigrane):
    """Pied de page : la société à gauche, l'extrait des conditions à droite ; mention en travers si besoin."""

    def decor(canvas, doc):
        canvas.saveState()
        if filigrane:
            canvas.setFont("Helvetica-Bold", 70)
            canvas.setFillColor(colors.Color(0.85, 0.1, 0.1, alpha=0.18))
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, filigrane)
            canvas.restoreState()
            canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#c9a227"))
        canvas.line(15 * mm, 30 * mm, A4[0] - 15 * mm, 30 * mm)
        lignes = [f"<b>{societe.nom}</b>", societe.forme_capital, f"Siège social : {societe.adresse}" if societe.adresse else "",
                  " / ".join(filter(None, [f"RCCM {societe.rccm}" if societe.rccm else "",
                                           f"CC N°{societe.compte_contribuable}" if societe.compte_contribuable else ""])),
                  f"Tél : {societe.telephone}" if societe.telephone else "", f"Email : {societe.email}" if societe.email else "",
                  societe.banque]
        largeur = A4[0] - 30 * mm
        gauche = Paragraph("<br/>".join(l for l in lignes if l), PETIT)
        _, h = gauche.wrap(largeur * 0.33, 24 * mm)
        gauche.drawOn(canvas, 15 * mm, 28 * mm - h)
        if extrait:
            droite = Paragraph(extrait.replace("\n", " "), ParagraphStyle("extrait", parent=PETIT, alignment=TA_JUSTIFY))
            _, h = droite.wrap(largeur * 0.63, 24 * mm)
            droite.drawOn(canvas, 15 * mm + largeur * 0.37, 28 * mm - h)
        canvas.restoreState()

    return decor


def pdf_devis(devis) -> bytes:
    societe, reglage = Societe.courante(), ReglageCommercial.courant()
    S, totaux, client = devis.Statut, devis.totaux(), devis.client
    commande = devis.statut == S.ACCEPTE
    filigrane = {S.BROUILLON: "PROJET", S.ANNULE: "ANNULÉ", S.REFUSE: "REFUSÉ"}.get(devis.statut)
    tampon = BytesIO()
    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm,
                            bottomMargin=34 * mm, title=f"{'Commande client' if commande else 'Devis'} {devis.numero}",
                            author=societe.nom)
    largeur = doc.width
    e = [_entete(societe, client, largeur)]
    if client.numero_contribuable:
        e.append(Table([["", Paragraph(f"N° contribuable : {client.numero_contribuable}", BASE)]], colWidths=[largeur * 0.5] * 2))
    e.append(Spacer(1, 6 * mm))
    e.append(Table(
        [[Paragraph(f"{'COMMANDE CLIENT' if commande else 'DEVIS'} N° {devis.numero}", TITRE),
          Paragraph(f"N° Client : {client.code}", TITRE),
          Paragraph(f"Date : {date_fr(devis.date)}", ParagraphStyle("d", parent=TITRE, alignment=TA_RIGHT))]],
        colWidths=[largeur * 0.5, largeur * 0.25, largeur * 0.25],
        style=[("LINEBELOW", (0, 0), (-1, -1), 0.8, colors.black), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    e.append(Spacer(1, 3 * mm))

    retour = timezone.localtime(devis.date_retour).strftime("%d/%m/%Y à %Hh%M") if devis.date_retour else "--"
    infos = [
        ["Type de loyer", Paragraph(f"<b>{devis.get_type_loyer_display().upper()}</b>", BASE),
         Paragraph("<b>Date de retour prévue</b>", BASE), Paragraph(f"<b>{retour}</b>", BASE)],
        ["Servi par", Paragraph(f"<b>{str(devis.commercial).upper()}</b>", BASE),
         Paragraph("<b>Mode fact.</b>", BASE), Paragraph(f"<b>{devis.get_mode_facturation_display().upper()}</b>", BASE)],
        ["Agence", devis.site.nom.upper(), "Début prévu" if devis.date_debut else "", date_fr(devis.date_debut) if devis.date_debut else ""],
    ]
    if commande and devis.reference_client:
        infos.append(["Votre commande", devis.reference_client, "Acceptée le", date_fr(devis.accepte_le)])
    elif not commande:
        infos.append(["Valable jusqu'au", date_fr(devis.validite), "", ""])
    if devis.lieu:
        infos.append(["Lieu d'utilisation", Paragraph(devis.lieu, BASE), "", ""])
    infos.append([Paragraph("<b>Libellé</b>", BASE), Paragraph(f"<b>{devis.libelle.upper()}</b>", BASE), "", ""])
    e.append(Table(infos, colWidths=[largeur * 0.17, largeur * 0.33, largeur * 0.2, largeur * 0.3],
                   style=[("FONT", (0, 0), (-1, -1), "Helvetica", 9), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                          ("SPAN", (1, len(infos) - 1), (3, len(infos) - 1)),
                          ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 1)]))
    e.append(Spacer(1, 3 * mm))

    corps = [["Quantité", "Référence / Désignation", "Prix Unit HT", "Remise", "P.U. Net", "Durée", "Montant HT"]]
    for l in devis.lignes.all():
        designation = l.designation + (f"<br/><font size=7>{l.materiel}</font>" if l.materiel_id else "")
        corps.append([quantite(l.quantite), Paragraph(designation, BASE), formate(l.prix_unitaire),
                      f"{quantite(l.remise)} %" if l.remise else "", formate(l.prix_net), quantite(l.duree), formate(l.montant_ht)])
    e.append(Table(corps, repeatRows=1,
                   colWidths=[largeur * 0.09, largeur * 0.39, largeur * 0.13, largeur * 0.08, largeur * 0.11, largeur * 0.07, largeur * 0.13],
                   style=TableStyle([
                       ("FONT", (0, 0), (-1, -1), "Helvetica", 9), ("FONT", (0, 1), (0, -1), "Helvetica-Bold", 9),
                       ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.black), ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
                       ("LINEBELOW", (0, -1), (-1, -1), 0.8, colors.black), ("ALIGN", (0, 0), (0, -1), "CENTER"),
                       ("ALIGN", (1, 0), (1, 0), "CENTER"), ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                       ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 1), (-1, -1), 5), ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
                   ])))
    if devis.conditions:
        e += [Spacer(1, 4 * mm), Paragraph("<b>Conditions particulières</b>", BASE),
              Paragraph(devis.conditions.replace("\n", "<br/>"), BASE)]
    e.append(Spacer(1, 10 * mm))

    taux = "Exonéré" if devis.exonere_tva else f"{quantite(totaux['taux_tva'])} %"
    recap = [["TVA%", "Montant HT", "Remises", "Base HT", "Montant TVA", "Montant TTC"],
             [taux, formate(totaux["total_ht"]), "", formate(totaux["total_ht"]), formate(totaux["total_tva"]) if totaux["total_tva"] else "",
              formate(totaux["total_ttc"])]]
    bas = [
        Table(recap, colWidths=[largeur / 6] * 6,
              style=[("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5), ("FONT", (0, 1), (-1, 1), "Helvetica", 9),
                     ("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.black),
                     ("LINEBELOW", (0, 1), (-1, 1), 0.5, colors.black)]),
        Table([[Paragraph("<b>Echéance</b>", BASE), Paragraph(f"<b>{devis.echeance.upper()}</b>", BASE),
                Paragraph("<b>Règlement</b>", BASE), Paragraph(f"<b>{devis.get_mode_reglement_display().upper()}</b>", BASE),
                Paragraph("<b>Total HT</b>", TITRE), Paragraph(f"<b>{formate(totaux['total_ht'])}</b>", ParagraphStyle("t", parent=TITRE, alignment=TA_RIGHT))],
               ["", "", "", "", Paragraph("<b>Total TTC</b>", TITRE), Paragraph(f"<b>{formate(totaux['total_ttc'])}</b>", ParagraphStyle("t2", parent=TITRE, alignment=TA_RIGHT))],
               ["", "", "", "", "Devise", Paragraph("XOF", DROITE)]],
              colWidths=[largeur * 0.11, largeur * 0.22, largeur * 0.12, largeur * 0.15, largeur * 0.2, largeur * 0.2],
              style=[("FONT", (0, 0), (-1, -1), "Helvetica", 9), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                     ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]),
        Table([[Paragraph(totaux["en_lettres"].upper(), BASE)]], colWidths=[largeur],
              style=[("LINEABOVE", (0, 0), (-1, -1), 0.5, colors.black), ("LINEBELOW", (0, 0), (-1, -1), 1, colors.black)]),
        Spacer(1, 2 * mm),
        Table([[Paragraph("NOM DU SIGNATAIRE", CENTRE), Paragraph("DATE ET HEURE - SIGNATURE CLIENT", CENTRE),
                Paragraph("NOTRE SIGNATURE", CENTRE)]], colWidths=[largeur * 0.3, largeur * 0.4, largeur * 0.3]),
        Spacer(1, 22 * mm),
    ]
    from reportlab.platypus import KeepTogether

    e.append(KeepTogether(bas))
    decor = _decor(societe, reglage.extrait_conditions, filigrane)
    doc.build(e, onFirstPage=decor, onLaterPages=decor)
    return _avec_conditions(tampon.getvalue(), reglage)


def _avec_conditions(pdf: bytes, reglage) -> bytes:
    """Ajoute à la suite le PDF des conditions générales chargé dans l'administration, s'il y en a un de lisible."""
    if not reglage.conditions_generales:
        return pdf
    from pypdf import PdfReader, PdfWriter

    try:
        resultat = PdfWriter()
        resultat.append(PdfReader(BytesIO(pdf)))
        with reglage.conditions_generales.open("rb") as f:
            resultat.append(PdfReader(f))
        sortie = BytesIO()
        resultat.write(sortie)
        return sortie.getvalue()
    except Exception:   # un fichier abîmé ne doit pas empêcher de sortir le devis
        return pdf
