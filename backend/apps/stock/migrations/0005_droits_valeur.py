from django.db import migrations


def donner_droits(apps, schema_editor):
    from apps.achats.roles import completer_roles
    from apps.stock.roles import DROITS_VALEUR

    completer_roles(apps, DROITS_VALEUR, applications=("stock",))


class Migration(migrations.Migration):
    dependencies = [("stock", "0004_valeur_stock"), ("contenttypes", "0002_remove_content_type_name"),
                    ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(donner_droits, migrations.RunPython.noop)]
