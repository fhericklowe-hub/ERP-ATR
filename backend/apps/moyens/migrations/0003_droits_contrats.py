from django.db import migrations


def donner_droits(apps, schema_editor):
    from apps.achats.roles import completer_roles
    from apps.moyens.roles import CONTRATS

    completer_roles(apps, {"Moyens généraux - Gestionnaire": CONTRATS}, applications=("moyens",))


class Migration(migrations.Migration):
    dependencies = [("moyens", "0002_contrats_echeances"), ("contenttypes", "0002_remove_content_type_name"),
                    ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(donner_droits, migrations.RunPython.noop)]
