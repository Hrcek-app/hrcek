"""Error codes owned by the collections app."""

from django.utils.translation import gettext_lazy as _

from hrcek.core.errors import register

NOT_YOURS = register("HRC-COLL-0001", 404, _("That entry is not yours to collect."))
NOT_A_MANUAL_COLLECTION = register(
    "HRC-COLL-0002",
    422,
    _("This collection follows a label, so entries cannot be added by hand."),
)
NOT_A_WISH_LIST = register(
    "HRC-COLL-0003", 404, _("This collection is not a shared wish list.")
)
OWN_WISH_LIST = register(
    "HRC-COLL-0004", 403, _("You cannot say “Got it” on your own wish list.")
)
NOT_ON_THE_LIST = register("HRC-COLL-0005", 404, _("That item is not on this list."))
ALREADY_GOT = register("HRC-COLL-0006", 409, _("Somebody else has already got this."))
NOT_YOURS_TO_UNDO = register(
    "HRC-COLL-0007", 403, _("Only whoever got this can undo it.")
)
