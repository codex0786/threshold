"""Admission routes beyond JEE."""
from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Institution, InstitutionAlias
from app.services import academics, exam_routes

router = APIRouter(prefix="/api/v1/exams")


def find(code: str) -> dict:
    route = next((r for r in exam_routes.load()["routes"] if r["code"] == code), None)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


def _name_key(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower().replace("&", "and"))


def institute_links(db: Session) -> dict[str, Institution]:
    """JoSAA institutes by exact official name or alias, ignoring case, spacing and punctuation. A name that
    fits more than one institute links to none."""
    found: dict[str, set[int]] = {}
    by_id: dict[int, Institution] = {}
    for inst in db.scalars(select(Institution)):
        by_id[inst.id] = inst
        found.setdefault(_name_key(inst.official_name), set()).add(inst.id)
    for alias in db.scalars(select(InstitutionAlias)):
        found.setdefault(_name_key(alias.alias), set()).add(alias.institution_id)
    return {key: by_id[next(iter(ids))] for key, ids in found.items() if len(ids) == 1}


@router.get("")
def routes() -> dict:
    data = exam_routes.load()
    return {"routes": [exam_routes.summary(r) for r in data["routes"]]}


@router.get("/{code}/shortlist")
def shortlist(
    code: str, value: float | None = Query(default=None, gt=0), category: str | None = None, quota: str | None = None,
    programme: str | None = None, gender: Literal["female", "male", "other"] | None = None,
    order: Literal["top", "closest"] = "top", search: str | None = None, db: Session = Depends(get_db),
) -> dict:
    route = find(code)
    problem = None if value is None else exam_routes.invalid_value(route, value)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    result = exam_routes.shortlist(route, value, category, quota, programme, gender, order, search)
    if result["options"]:
        links = institute_links(db)
        profiles = academics.load(db)
        for option in result["options"]:
            inst = links.get(_name_key(option["institute"]))
            option["institution"] = None if inst is None else {
                "slug": inst.slug, "short_name": inst.short_name, "type": inst.institute_type, "state": inst.state,
                "academics": academics.summary(profiles.get(inst.id)),
            }
    return result


@router.get("/{code}")
def route_records(
    code: str, value: float | None = Query(default=None, gt=0), category: str | None = None, group: str | None = None,
    search: str | None = None, programme: str | None = None, limit: int = Query(default=50, ge=1, le=200),
    order: Literal["top", "closest"] = "top", gender: Literal["female", "male", "other"] | None = None,
    eligible: list[str] = Query(default=[]),
) -> dict:
    route = find(code)
    problem = None if value is None else exam_routes.invalid_value(route, value)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    return exam_routes.query(route, value, category, group, search, limit, programme, order, gender, frozenset(eligible))
