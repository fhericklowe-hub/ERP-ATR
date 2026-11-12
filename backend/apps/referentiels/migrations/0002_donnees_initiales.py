from django.db import migrations

UNITES = [("U", "Unité"), ("L", "Litre"), ("KG", "Kilogramme"), ("M", "Mètre"), ("H", "Heure"), ("J", "Jour"), ("T", "Tonne"), ("KM", "Kilomètre")]


def creer(apps, schema_editor):
    Unite = apps.get_model("referentiels", "Unite")
    Emplacement = apps.get_model("referentiels", "Emplacement")
    Site = apps.get_model("core", "Site")
    for code, nom in UNITES:
        Unite.objects.get_or_create(code=code, defaults={"nom": nom})
    # Chaque site de l'entreprise est aussi un emplacement possible pour un équipement.
    for site in Site.objects.all():
        Emplacement.objects.get_or_create(type="SITE", site=site, defaults={"nom": site.nom, "ville": site.ville})


class Migration(migrations.Migration):
    dependencies = [("referentiels", "0001_initial"), ("core", "0002_donnees_initiales")]
    operations = [migrations.RunPython(creer, migrations.RunPython.noop)]
