"""Admission routes beyond JEE."""
from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Institution, InstitutionAlias
from pydantic import BaseModel, Field

from app.services import academics, exam_lists, exam_routes

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
    # Routes whose rules and round-by-round history support a choice list and round advice.
    return {"routes": [{**exam_routes.summary(r), "list_tools": exam_lists.supported(r)} for r in data["routes"]]}


Short = Field(max_length=400)


class ListBuildRequest(BaseModel):
    value: int = Field(gt=0, le=10_000_000)
    category: str = Field(max_length=60)
    quotas: list[str] = Field(min_length=1, max_length=40)
    programmes: list[str] = Field(default=[], max_length=10)
    gender: Literal["female", "male", "other"] | None = None
    size: int = Field(default=60, ge=5, le=300)
    safety_net: int = Field(default=5, ge=0, le=20)
    include_ambitious: bool = True
    past_safety_net: bool = False


class ListItem(BaseModel):
    institute: str = Short
    institute_short: str | None = Field(default=None, max_length=400)
    programme: str = Short
    quota: str = Short
    key: str | None = Field(default=None, max_length=400)


class RoundAdviceRequest(BaseModel):
    value: int = Field(gt=0, le=10_000_000)
    items: list[ListItem] = Field(min_length=1, max_length=300)
    allotted_index: int = Field(ge=0)
    round: int = Field(ge=1, le=4)


def _list_route(code: str) -> dict:
    route = find(code)
    if not exam_lists.supported(route):
        raise HTTPException(status_code=404, detail="Choice lists and round advice aren't available for this route yet.")
    return route


@router.post("/{code}/list/build")
def build_list(code: str, request: ListBuildRequest) -> dict:
    route = _list_route(code)
    return exam_lists.build(route, request.value, request.category, request.quotas, request.programmes or None, request.gender,
                            request.size, request.safety_net, request.include_ambitious, request.past_safety_net)


@router.post("/{code}/list/advice")
def round_advice(code: str, request: RoundAdviceRequest) -> dict:
    route = _list_route(code)
    try:
        return exam_lists.advise(route, request.value, [i.model_dump() for i in request.items], request.allotted_index, request.round)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/{code}/shortlist")
def shortlist(
    code: str, value: float | None = Query(default=None, gt=0), category: str | None = None, quota: str | None = None,
    programme: str | None = None, gender: Literal["female", "male", "other"] | None = None,
    order: Literal["top", "closest"] = "top", search: str | None = None, db: Session = Depends(get_db),
    merit: int | None = Query(default=None, gt=0, le=10_000_000, description="State merit number, where the route's bands use it"),
) -> dict:
    route = find(code)
    problem = None if value is None else exam_routes.invalid_value(route, value)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    result = exam_routes.shortlist(route, value, category, quota, programme, gender, order, search, merit)
    profiles = exam_routes.load().get("profiles", {}).get(code, {})
    for option in result["options"]:
        profile = profiles.get(option["institute"])
        option["profile"] = profile
        # A seat's own fee comes first. Otherwise the university's published fee applies to the whole institute.
        if not option.get("fee") and profile and profile.get("fee"):
            option["fee"] = profile["fee"]
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
