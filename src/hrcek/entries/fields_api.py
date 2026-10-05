"""Reading what an account has defined.

Fields and labels are their own resources rather than something under
an entry: a client asking "what fields do I have?" is not asking about
any particular entry. Both are read-only here — they are created and
renamed through the web pages.
"""

from __future__ import annotations

from typing import Any, cast

from django.db.models import QuerySet
from django.db.models.functions import Lower
from django.http import HttpRequest
from ninja import Field, Router, Schema
from ninja.pagination import LimitOffsetPagination, PaginationBase, paginate

from hrcek.accounts.models import User
from hrcek.entries.models import FieldDefinition, Tag
from hrcek.entries.schemas import FieldOut, LabelOut

# One page holds every label a family-scale account is likely to have,
# so a client can ask once and filter locally if it wants to. It is
# both the default and the ceiling: asking plainly returns everything
# up to this many, and asking for more than this returns this many.
LABELS_PER_PAGE = 1000


class LabelPagination(PaginationBase):
    """Paged by the last name seen, not by an offset.

    Labels are ordered alphabetically, so "everything after this one"
    is all a client needs to carry between pages — and unlike an
    offset it stays correct while the list changes underneath. Add a
    label that sorts earlier and an offset pushes a row across the
    page boundary, where the next request skips it; a cursor does not
    move.
    """

    class Input(Schema):
        limit: int = Field(LABELS_PER_PAGE, ge=1, le=LABELS_PER_PAGE)
        after: str = ""

    class Output(Schema):
        items: list[LabelOut]
        count: int

    items_attribute = "items"

    def paginate_queryset(
        self,
        queryset: QuerySet,
        pagination: Any,
        request: HttpRequest,
        **params: Any,
    ) -> dict[str, Any]:
        # count before the cursor narrows it: a client wants to know
        # how many labels match, not how many are left to read.
        total = queryset.count()
        after = pagination.after.strip()
        if after:
            # casefold, matching the ordering exactly. Compare any
            # other way and a page boundary lands between two rows
            # that the ordering puts the other way round.
            queryset = queryset.filter(sort_key__gt=after.casefold())
        return {"items": queryset[: pagination.limit], "count": total}


fields_router = Router(tags=["fields"])
labels_router = Router(tags=["labels"])


@fields_router.get("/", response=list[FieldOut], operation_id="list_fields")
@paginate(LimitOffsetPagination)
def list_fields(request: HttpRequest) -> QuerySet[FieldDefinition]:
    """The fields this account's entries may carry.

    A client reads these to build its own inputs: the kind says what
    sort of value is wanted, and a choice field's options say what the
    choices are.
    """
    owner = cast("User", request.user)
    return FieldDefinition.objects.filter(owner=owner)


@labels_router.get("/", response=list[LabelOut], operation_id="list_labels")
@paginate(LabelPagination)
def list_labels(request: HttpRequest, starts_with: str = "") -> QuerySet[Tag]:
    """This account's labels, optionally those beginning with a string.

    The same endpoint serves a full list and an autocomplete, because
    they differ only by a filter. `count` is how many labels match,
    not how many this page carries, so a client knows whether to ask
    for more.
    """
    owner = cast("User", request.user)
    # Ordered by the lowercased name, which is what a reader expects
    # and what the cursor compares against. A label cannot differ from
    # another only by case — the unique constraint sees to that — so
    # this is a strict order with no ties to break.
    labels = Tag.in_use(owner).annotate(sort_key=Lower("name")).order_by("sort_key")
    prefix = starts_with.strip()
    if prefix:
        # istartswith, not a pattern: whatever somebody types into an
        # autocomplete box is a literal, punctuation included.
        labels = labels.filter(name__istartswith=prefix)
    return labels
