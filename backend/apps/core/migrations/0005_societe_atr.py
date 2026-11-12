from django.db import migrations


def creer(apps, schema_editor):
    Societe = apps.get_model("core", "Societe")
    Societe.objects.get_or_create(pk=1, defaults=dict(
        nom="ATELIER TECHNIQUE DE REPARATION",
        forme_capital="SARL au Capital de 1.710.000.000 FCFA",
        adresse="Abidjan-Yopougon, Autoroute du nord PK23, 18 BP 2946 Abidjan 18 Côte d'Ivoire",
        rccm="CI-ABJ-1999-B-243733",
        compte_contribuable="9908512B",
        regime_imposition="REEL NORMAL",
        centre_impots="DGE",
        telephone="(+225) 27 23 40 80 35 - Mob : 07 69 00 00 29",
        email="info@atrci.com",
        banque="SGBCI : CI0080111601168445791666",
    ))


class Migration(migrations.Migration):
    dependencies = [("core", "0004_societe")]
    operations = [migrations.RunPython(creer, migrations.RunPython.noop)]
