from django.db import migrations


def donner_droits(apps, schema_editor):
    from apps.achats.roles import completer_roles
    from apps.hse.roles import DROITS_TERRAIN

    completer_roles(apps, DROITS_TERRAIN, applications=("hse",))


class Migration(migrations.Migration):
    dependencies = [("hse", "0002_visites_epi"), ("contenttypes", "0002_remove_content_type_name"),
                    ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(donner_droits, migrations.RunPython.noop)]
