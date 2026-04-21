"""
Engagement CRUD API routes.

    GET    /api/engagements              → list all
    GET    /api/engagements/{id}         → get one
    POST   /api/engagements              → create
    PATCH  /api/engagements/{id}         → update
    DELETE /api/engagements/{id}         → delete

These are the building blocks the frontend needs to let the user pick
their engagement and its currency. Other routes read-through via
engagements.get_engagement() — this router owns writes only.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel, Field

from engagements import (
    EngagementConfig,
    get_engagement,
    list_engagements,
    create_engagement,
    update_engagement,
    delete_engagement,
    DEFAULT_ENGAGEMENT_ID,
)
from currency import UnsupportedCurrency, CURRENCY_TABLE
from auth import require_client_or_editor, require_editor


router = APIRouter(prefix="/api/engagements", tags=["engagements"])


class EngagementCreateBody(BaseModel):
    id: str = Field(..., min_length=1, max_length=80,
                    description="URL-safe identifier, e.g. 'acme-q2-2024'")
    name: str = Field(..., min_length=1, max_length=200)
    currency: str = "USD"
    locale: str = "en-US"


class EngagementUpdateBody(BaseModel):
    name: Optional[str] = None
    currency: Optional[str] = None
    locale: Optional[str] = None


def _serialize(e: EngagementConfig) -> dict:
    return e.as_dict()


@router.get("")
def list_all(user=Depends(require_client_or_editor)):
    """
    List all engagements. Also returns the supported-currency catalog so
    frontends can populate dropdowns without making a second call.
    """
    return {
        "engagements": [_serialize(e) for e in list_engagements()],
        "default_id": DEFAULT_ENGAGEMENT_ID,
        "supported_currencies": sorted(CURRENCY_TABLE),
    }


@router.get("/{engagement_id}")
def get_one(engagement_id: str, user=Depends(require_client_or_editor)):
    e = get_engagement(engagement_id)
    # get_engagement falls back to default on miss — detect that here
    # and return 404 so the client knows the id was bad
    if engagement_id != DEFAULT_ENGAGEMENT_ID and e.id == DEFAULT_ENGAGEMENT_ID:
        raise HTTPException(404, f"Engagement {engagement_id!r} not found")
    return _serialize(e)


@router.post("", status_code=201)
def create(body: EngagementCreateBody, user=Depends(require_editor)):
    try:
        e = create_engagement(
            id=body.id, name=body.name,
            currency=body.currency, locale=body.locale,
        )
    except UnsupportedCurrency as e:
        raise HTTPException(422, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    return _serialize(e)


@router.patch("/{engagement_id}")
def update(engagement_id: str, body: EngagementUpdateBody,
           user=Depends(require_editor)):
    try:
        e = update_engagement(
            engagement_id,
            name=body.name, currency=body.currency, locale=body.locale,
        )
    except UnsupportedCurrency as err:
        raise HTTPException(422, str(err))
    except ValueError as err:
        raise HTTPException(404, str(err))
    return _serialize(e)


@router.delete("/{engagement_id}", status_code=204)
def delete(engagement_id: str, user=Depends(require_editor)):
    if engagement_id == DEFAULT_ENGAGEMENT_ID:
        raise HTTPException(400, "Cannot delete the default engagement")
    ok = delete_engagement(engagement_id)
    if not ok:
        raise HTTPException(404, f"Engagement {engagement_id!r} not found")
    return
