from django.db import migrations

from apps.achats.roles import completer_roles


def completer(apps, schema_editor):
    completer_roles(apps, {"Technique - Chef d'atelier": [
        "technique.voir_couts_ordrereparation", "technique.view_reglageatelier", "technique.change_reglageatelier",
        "technique.add_reglageatelier",
    ]}, applications=("technique",))


class Migration(migrations.Migration):
    dependencies = [("technique", "0002_temps_et_couts"), ("contenttypes", "0002_remove_content_type_name"),
                    ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(completer, migrations.RunPython.noop)]
