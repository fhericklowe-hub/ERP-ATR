from django.db import migrations


def donner_droits(apps, schema_editor):
    from apps.achats.roles import FACTURES, completer_roles

    completer_roles(apps, FACTURES)


class Migration(migrations.Migration):
    dependencies = [("achats", "0011_facture_fournisseur"), ("contenttypes", "0002_remove_content_type_name"),
                    ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(donner_droits, migrations.RunPython.noop)]
