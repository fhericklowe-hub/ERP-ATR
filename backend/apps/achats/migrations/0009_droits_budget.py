from django.db import migrations


def donner_droits(apps, schema_editor):
    from apps.achats.roles import BUDGET, completer_roles

    completer_roles(apps, BUDGET, applications=("achats", "referentiels"))


class Migration(migrations.Migration):
    dependencies = [("achats", "0008_demandes_budget"), ("referentiels", "0004_comptes_de_charge"),
                    ("contenttypes", "0002_remove_content_type_name"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(donner_droits, migrations.RunPython.noop)]
