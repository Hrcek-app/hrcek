from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class OpsConfig(AppConfig):
    name = "hrcek.ops"
    verbose_name = _("Operations")
