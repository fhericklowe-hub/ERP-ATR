from django.db import migrations


def donner_droits(apps, schema_editor):
    from apps.achats.roles import completer_roles
    from apps.commercial.roles import DROITS_OPPORTUNITE

    completer_roles(apps, DROITS_OPPORTUNITE, applications=("commercial",))


class Migration(migrations.Migration):
    dependencies = [("commercial", "0002_opportunites"), ("contenttypes", "0002_remove_content_type_name"),
                    ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(donner_droits, migrations.RunPython.noop)]
