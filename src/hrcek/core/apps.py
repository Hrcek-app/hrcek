from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules
from django.utils.translation import gettext_lazy as _

from hrcek.core.translations import compile_at_startup


class CoreConfig(AppConfig):
    name = "hrcek.core"
    verbose_name = _("Core")

    def ready(self) -> None:
        # Import every app's ``errors`` module so all codes are
        # registered — and any duplicate raises — at startup rather
        # than on the first request that happens to need one.
        autodiscover_modules("errors")

        # The compiled catalogues are built, not committed. The Docker
        # image builds them; any other install builds them here, on
        # first start and after every change to a .po file.
        compile_at_startup()
