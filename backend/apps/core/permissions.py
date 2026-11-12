from rest_framework.permissions import DjangoModelPermissions


class DroitsModele(DjangoModelPermissions):
    """Comme DjangoModelPermissions, mais la lecture exige aussi le droit « voir »."""

    perms_map = {
        **DjangoModelPermissions.perms_map,
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": [],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
    }
