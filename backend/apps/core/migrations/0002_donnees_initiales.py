from django.db import migrations

SITES = [
    ("SIEGE", "Siège", "", True),
    ("MARCORY", "Marcory", "Abidjan", False),
    ("SANPEDRO", "San Pedro", "San Pedro", False),
    ("FERKE", "Ferké", "Ferkessédougou", False),
]
SERVICES = [
    ("DG", "Direction générale"),
    ("ACH", "Achats"),
    ("MG", "Moyens généraux"),
    ("STK", "Stock et logistique"),
    ("TECH", "Technique"),
    ("COM", "Commercial"),
    ("EXP", "Exploitation"),
    ("RH", "Ressources humaines"),
    ("HSE", "HSE"),
    ("FIN", "Finances"),
]


def creer(apps, schema_editor):
    Site = apps.get_model("core", "Site")
    Service = apps.get_model("core", "Service")
    for code, nom, ville, siege in SITES:
        Site.objects.get_or_create(code=code, defaults={"nom": nom, "ville": ville, "est_siege": siege})
    for code, nom in SERVICES:
        Service.objects.get_or_create(code=code, defaults={"nom": nom})


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunPython(creer, migrations.RunPython.noop)]
