"""Mise en page PDF des bons de commande et de réception, calquée sur les documents actuels."""
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.core.devises import formate
from apps.core.lettres import montant_en_lettres
from apps.core.models import Societe

BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=9, leading=11)
GRAS = ParagraphStyle("gras", parent=BASE, fontName="Helvetica-Bold")
TITRE = ParagraphStyle("titre", parent=GRAS, fontSize=11, leading=14)
DROITE = ParagraphStyle("droite", parent=BASE, alignment=TA_RIGHT)
PIED = ParagraphStyle("pied", parent=BASE, fontSize=7, leading=9, alignment=TA_CENTER)


def quantite(q) -> str:
    return f"{q.normalize():f}".replace(".", ",")


def date_fr(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "--"


def _decor(societe, filigrane=None):
    """Pied de page de la société et, si besoin, mention en travers de la page (PROJET, ANNULÉ)."""

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

    return decor


def _entete(societe, tiers, largeur):
    """Société (logo et mentions fiscales) à gauche, tiers à droite."""
    logo = Image(societe.chemin_logo, width=42 * mm, height=30 * mm, kind="proportional")
    logo.hAlign = "LEFT"
    fiscal = [f"N° CC : <b>{societe.compte_contribuable}</b>" if societe.compte_contribuable else "",
              f"Régime d'imposition : <b>{societe.regime_imposition}</b>" if societe.regime_imposition else "",
              f"Centre des impôts : <b>{societe.centre_impots}</b>" if societe.centre_impots else ""]
    gauche = [logo, Paragraph("<br/>".join(x for x in fiscal if x), ParagraphStyle("f", parent=BASE, fontSize=7, leading=9))]
    droite = [Paragraph(tiers.raison_sociale, TITRE),
              Paragraph("<br/>".join(x for x in [tiers.adresse.replace("\n", "<br/>"), tiers.ville,
                                                  f"Téléphone : {tiers.telephone}" if tiers.telephone else ""] if x), BASE)]
    return Table([[gauche, droite]], colWidths=[largeur * 0.5, largeur * 0.5], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])


def pdf_bon_commande(bon) -> bytes:
    societe = Societe.courante()
    totaux = bon.totaux()
    tampon = BytesIO()

    def nombre(n):
        return formate(n, bon.devise)

    # Sans ses deux validations, le document ne doit pas pouvoir passer pour un bon définitif.
    filigrane = None if bon.definitif else ("ANNULÉ" if bon.statut == bon.Statut.ANNULE else "PROJET")
    decor = _decor(societe, filigrane)

    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=15 * mm,
                            bottomMargin=30 * mm, title=f"Bon de commande {bon.numero}", author=societe.nom)
    largeur = doc.width
    f = bon.fournisseur
    elements = []

    elements.append(_entete(societe, f, largeur))
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
           ["Total TTC", nombre(totaux["total_ttc"])], ["Devise", bon.devise]]
    bloc_tot = Table(tot, colWidths=[largeur * 0.2, largeur * 0.2],
                     style=[("FONT", (0, 0), (-1, -1), "Helvetica-Bold", 10), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                            ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.black)])
    elements.append(Table([[bloc_tva, bloc_tot]], colWidths=[largeur * 0.6, largeur * 0.4],
                          style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    if bon.devise != "XOF" and totaux["contre_valeur_xof"] is not None:
        cours = f"{bon.taux_change.normalize():f}".replace(".", ",")
        elements.append(Paragraph(f"Contre-valeur : {formate(totaux['contre_valeur_xof'])} XOF (1 {bon.devise} = {cours} XOF)", BASE))
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


def pdf_bon_reception(bon) -> bytes:
    societe = Societe.courante()
    commande = bon.commande
    f = commande.fournisseur
    tampon = BytesIO()

    def nombre(n):
        return formate(n, commande.devise)

    S = bon.Statut
    filigrane = {S.BROUILLON: "PROJET", S.ANNULE: "ANNULÉ"}.get(bon.statut)
    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=15 * mm,
                            bottomMargin=30 * mm, title=f"Bon de réception {bon.numero}", author=societe.nom)
    largeur = doc.width
    elements = [_entete(societe, f, largeur), Spacer(1, 8 * mm)]

    elements.append(Table(
        [[Paragraph(f"BON DE RÉCEPTION N° {bon.numero}", TITRE), Paragraph(f"N° fournisseur : {f.code}", TITRE),
          Paragraph(f"Date : {date_fr(bon.date)}", ParagraphStyle("d", parent=TITRE, alignment=TA_RIGHT))]],
        colWidths=[largeur * 0.47, largeur * 0.28, largeur * 0.25],
    ))
    sous = [f"<b>N° livraison fournisseur : {bon.numero_livraison or '--'}</b>"]
    if bon.ancien_numero:
        sous.append(f"N° ancien logiciel : {bon.ancien_numero}")
    elements.append(Paragraph(" &nbsp;·&nbsp; ".join(sous), BASE))
    elements.append(Table([[""]], colWidths=[largeur], rowHeights=[2 * mm],
                          style=[("LINEBELOW", (0, 0), (-1, -1), 0.8, colors.black)]))
    elements.append(Spacer(1, 3 * mm))

    infos = [
        ["N° commande", Paragraph(f"<b>{commande.numero}</b>", BASE), "Libellé", commande.objet or "--"],
        ["Succ. débitée", commande.site.nom, "Service", f"{commande.service.code} - {commande.service.nom}"],
        ["Réceptionnaire", str(bon.receptionnaire).upper(), "Demande", commande.demande.numero],
    ]
    elements.append(Table(infos, colWidths=[largeur * 0.17, largeur * 0.35, largeur * 0.13, largeur * 0.35],
                          style=[("FONT", (0, 0), (-1, -1), "Helvetica", 9), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 1)]))
    elements.append(Spacer(1, 6 * mm))

    petit = ParagraphStyle("petit", parent=BASE, fontSize=8, leading=10)
    donnees = [["Commandé", "Reçu", "Référence / Désignation", "À mettre en stock", "Montant HT"]]
    for l in bon.lignes.all():
        lc = l.ligne_commande
        cellule = [Paragraph(f"{lc.reference} &nbsp; {lc.designation}" if lc.reference else lc.designation, BASE)]
        materiel = " &nbsp;·&nbsp; ".join(x for x in [f"N° matériel : <b>{l.numero_materiel}</b>" if l.numero_materiel else "",
                                                      f"N° série : <b>{l.numero_serie}</b>" if l.numero_serie else "",
                                                      f"Identité : <b>{l.immatriculation}</b>" if l.immatriculation else ""] if x)
        if materiel:
            cellule.append(Paragraph(materiel, petit))
        if l.observations:
            cellule.append(Paragraph(f"Observations : {l.observations}", petit))
        donnees.append([quantite(lc.quantite), quantite(l.quantite_recue), cellule, quantite(l.quantite_stock),
                        nombre(l.montant_ht)])
    elements.append(Table(
        donnees, repeatRows=1,
        colWidths=[largeur * 0.12, largeur * 0.1, largeur * 0.46, largeur * 0.17, largeur * 0.15],
        style=[("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9), ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
               ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.black), ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
               ("ALIGN", (0, 0), (1, -1), "CENTER"), ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
               ("VALIGN", (0, 0), (-1, -1), "TOP")],
    ))
    elements.append(Spacer(1, 8 * mm))

    total = bon.total_ht
    elements.append(Table([["", "Total HT reçu", nombre(total)], ["", "Devise", commande.devise]],
                          colWidths=[largeur * 0.6, largeur * 0.2, largeur * 0.2],
                          style=[("FONT", (0, 0), (-1, -1), "Helvetica-Bold", 10), ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                                 ("LINEABOVE", (1, 0), (-1, 0), 0.5, colors.black)]))
    elements.append(Table([[Paragraph(montant_en_lettres(total, commande.devise), BASE)]], colWidths=[largeur],
                          style=[("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.black),
                                 ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black)]))
    if bon.observations:
        elements.append(Spacer(1, 4 * mm))
        elements.append(Paragraph(f"<b>Observations :</b> {bon.observations}".replace("\n", "<br/>"), BASE))
    elements.append(Spacer(1, 8 * mm))

    if bon.statut == S.VALIDE:
        visa = f"Réception validée par {bon.receptionnaire} le {date_fr(timezone.localtime(bon.valide_le))}"
    elif bon.statut == S.ANNULE:
        visa = f"Réception annulée : {bon.motif_annulation}"
    else:
        visa = "Réception non validée"
    centre = ParagraphStyle("s", parent=BASE, alignment=TA_CENTER)
    elements.append(Table(
        [[Paragraph(visa, petit), Paragraph("<b>Visa du réceptionnaire</b>", centre), Paragraph("<b>Visa du livreur</b>", centre)]],
        colWidths=[largeur * 0.4, largeur * 0.3, largeur * 0.3], rowHeights=[25 * mm],
        style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (1, 0), (1, 0), 0.5, colors.grey),
               ("BOX", (2, 0), (2, 0), 0.5, colors.grey)],
    ))

    decor = _decor(societe, filigrane)
    doc.build(elements, onFirstPage=decor, onLaterPages=decor)
    return tampon.getvalue()
