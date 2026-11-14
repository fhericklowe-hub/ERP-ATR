from django.db import migrations


def donner_droits(apps, schema_editor):
    from apps.achats.roles import completer_roles
    from apps.core.roles import DROITS_JOURNAL

    completer_roles(apps, DROITS_JOURNAL, applications=("core",))


class Migration(migrations.Migration):
    dependencies = [("core", "0013_journal"), ("contenttypes", "0002_remove_content_type_name"),
                    ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(donner_droits, migrations.RunPython.noop)]
