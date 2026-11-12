from django.db import migrations


def donner_droits(apps, schema_editor):
    from apps.achats.roles import completer_roles
    from apps.stock.roles import DROITS_DEMANDES

    completer_roles(apps, DROITS_DEMANDES, applications=("stock",))


class Migration(migrations.Migration):
    dependencies = [("stock", "0002_demandes_sortie"), ("contenttypes", "0002_remove_content_type_name"),
                    ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(donner_droits, migrations.RunPython.noop)]
