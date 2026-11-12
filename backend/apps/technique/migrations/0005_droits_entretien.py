from django.db import migrations


def donner_droits(apps, schema_editor):
    from apps.achats.roles import completer_roles
    from apps.technique.roles import DROITS_ENTRETIEN

    completer_roles(apps, DROITS_ENTRETIEN, applications=("technique",))


class Migration(migrations.Migration):
    dependencies = [("technique", "0004_entretien_preventif"), ("contenttypes", "0002_remove_content_type_name"),
                    ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(donner_droits, migrations.RunPython.noop)]
