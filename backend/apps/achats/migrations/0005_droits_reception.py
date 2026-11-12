from django.db import migrations


def donner_droits(apps, schema_editor):
    """Donne les droits du bon de réception aux rôles créés avant lui. Sur une base neuve, rien à faire :
    les rôles sont créés complets après les migrations."""
    from django.contrib.auth.management import create_permissions
    from django.db.models import Q

    from apps.achats.roles import DROITS_RECEPTION

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    if not Group.objects.filter(name__in=DROITS_RECEPTION).exists():
        return
    config = apps.get_app_config("achats")
    config.models_module = True  # nécessaire pour créer les droits des nouveaux modèles dès maintenant
    create_permissions(config, apps=apps, verbosity=0)
    config.models_module = None
    for nom, droits in DROITS_RECEPTION.items():
        groupe = Group.objects.filter(name=nom).first()
        if not groupe:
            continue
        filtre = Q()
        for droit in droits:
            app, code = droit.split(".")
            filtre |= Q(content_type__app_label=app, codename=code)
        groupe.permissions.add(*Permission.objects.filter(filtre))


class Migration(migrations.Migration):
    dependencies = [("achats", "0004_bon_reception"), ("referentiels", "0001_initial"),
                    ("contenttypes", "0002_remove_content_type_name"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(donner_droits, migrations.RunPython.noop)]
