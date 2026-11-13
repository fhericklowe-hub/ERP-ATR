from django.db import migrations


def donner_droits(apps, schema_editor):
    from apps.achats.roles import completer_roles
    from apps.rh.roles import DROITS_ABSENCES

    completer_roles(apps, DROITS_ABSENCES, applications=("rh",))


class Migration(migrations.Migration):
    dependencies = [("rh", "0002_conges"), ("contenttypes", "0002_remove_content_type_name"),
                    ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(donner_droits, migrations.RunPython.noop)]
