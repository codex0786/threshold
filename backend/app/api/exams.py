"""Admission routes beyond JEE."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.services import exam_routes

router = APIRouter(prefix="/api/v1/exams")


def find(code: str) -> dict:
    route = next((r for r in exam_routes.load()["routes"] if r["code"] == code), None)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


@router.get("")
def routes() -> dict:
    data = exam_routes.load()
    return {"routes": [exam_routes.summary(r) for r in data["routes"]]}


@router.get("/{code}")
def route_records(
    code: str, value: float | None = Query(default=None, gt=0), category: str | None = None, group: str | None = None,
    search: str | None = None, programme: str | None = None, limit: int = Query(default=50, ge=1, le=200),
    order: Literal["top", "closest"] = "top", gender: Literal["female", "male", "other"] | None = None,
) -> dict:
    route = find(code)
    problem = None if value is None else exam_routes.invalid_value(route, value)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    return exam_routes.query(route, value, category, group, search, limit, programme, order, gender)
