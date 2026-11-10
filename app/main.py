import json

from app.ordering import CycleError, affected_by, creation_order
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from app.schemas import (
    DependencyCreate, DependencyOut, ResourceCreate, ResourceOut, ScanCreate, ScanOut,
)
from app.database import get_conn
from app.schemas import ResourceCreate, ResourceOut, ScanCreate, ScanOut

import logging
from app import cache

from fastapi import Request
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Cloud IaC Agent")

SCAN_COLS = "id, account_id, region, status, started_at"
RESOURCE_COLS = (
    "id, scan_id, resource_type, resource_id, name, config, monthly_cost_usd, created_at"
)


def get_scan_or_404(conn: Connection, scan_id: int) -> dict:
    row = conn.execute(
        text(f"SELECT {SCAN_COLS} FROM scans WHERE id = :id"), {"id": scan_id}
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")
    return dict(row)


@app.get("/health")
def health(conn: Connection = Depends(get_conn)):
    conn.execute(text("SELECT 1"))  # proves the database answers
    return {"status": "ok", "database": "connected"}


@app.post("/scans", response_model=ScanOut, status_code=201)
def create_scan(scan: ScanCreate, conn: Connection = Depends(get_conn)):
    row = conn.execute(
        text(
            "INSERT INTO scans (account_id, region) VALUES (:acc, :reg) "
            f"RETURNING {SCAN_COLS}"
        ),
        {"acc": scan.account_id, "reg": scan.region},
    ).mappings().one()
    logger.info("scan created id=%s region=%s", row["id"], scan.region)
    return dict(row)


@app.get("/scans", response_model=list[ScanOut])
def list_scans(conn: Connection = Depends(get_conn)):
    rows = conn.execute(
        text(f"SELECT {SCAN_COLS} FROM scans ORDER BY id")
    ).mappings().all()
    return [dict(r) for r in rows]


@app.get("/scans/{scan_id}", response_model=ScanOut)
def get_scan(scan_id: int, conn: Connection = Depends(get_conn)):
    return get_scan_or_404(conn, scan_id)


@app.post("/scans/{scan_id}/resources", response_model=ResourceOut, status_code=201)
def add_resource(
    scan_id: int, resource: ResourceCreate, conn: Connection = Depends(get_conn)
):
    get_scan_or_404(conn, scan_id)  # 404 if the scan doesn't exist
    row = conn.execute(
        text(
            "INSERT INTO resources "
            "(scan_id, resource_type, resource_id, name, config, monthly_cost_usd) "
            "VALUES (:sid, :rtype, :rid, :name, CAST(:config AS JSONB), :cost) "
            f"RETURNING {RESOURCE_COLS}"
        ),
        {
            "sid": scan_id,
            "rtype": resource.resource_type,
            "rid": resource.resource_id,
            "name": resource.name,
            "config": json.dumps(resource.config),
            "cost": resource.monthly_cost_usd,
        },
    ).mappings().one()
    cache.delete(f"scan:{scan_id}:summary", f"scan:{scan_id}:creation-order")
    return dict(row)


@app.get("/scans/{scan_id}/resources", response_model=list[ResourceOut])
def list_resources(
    scan_id: int,
    resource_type: str | None = None,  # optional filter: ?resource_type=s3_bucket
    conn: Connection = Depends(get_conn),
):
    get_scan_or_404(conn, scan_id)
    query = f"SELECT {RESOURCE_COLS} FROM resources WHERE scan_id = :sid"
    params: dict = {"sid": scan_id}
    if resource_type:
        query += " AND resource_type = :rtype"
        params["rtype"] = resource_type
    rows = conn.execute(text(query + " ORDER BY id"), params).mappings().all()
    return [dict(r) for r in rows]  

DEP_COLS = "id, scan_id, from_resource_id, to_resource_id, relationship"


@app.post("/scans/{scan_id}/dependencies", response_model=DependencyOut, status_code=201)
def add_dependency(
    scan_id: int, dep: DependencyCreate, conn: Connection = Depends(get_conn)
):
    get_scan_or_404(conn, scan_id)
    if dep.from_resource_id == dep.to_resource_id:
        raise HTTPException(status_code=422, detail="A resource cannot depend on itself")

    found = conn.execute(
        text("SELECT id FROM resources WHERE scan_id = :sid AND id IN (:a, :b)"),
        {"sid": scan_id, "a": dep.from_resource_id, "b": dep.to_resource_id},
    ).all()
    if len(found) != 2:
        raise HTTPException(
            status_code=404, detail="Both resources must exist in this scan"
        )

    try:
        row = conn.execute(
            text(
                "INSERT INTO resource_dependencies "
                "(scan_id, from_resource_id, to_resource_id, relationship) "
                f"VALUES (:sid, :a, :b, :rel) RETURNING {DEP_COLS}"
            ),
            {
                "sid": scan_id,
                "a": dep.from_resource_id,
                "b": dep.to_resource_id,
                "rel": dep.relationship,
            },
        ).mappings().one()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="This dependency already exists")
    cache.delete(f"scan:{scan_id}:creation-order")
    return dict(row)


@app.get("/scans/{scan_id}/dependencies", response_model=list[DependencyOut])
def list_dependencies(scan_id: int, conn: Connection = Depends(get_conn)):
    get_scan_or_404(conn, scan_id)
    rows = conn.execute(
        text(f"SELECT {DEP_COLS} FROM resource_dependencies WHERE scan_id = :sid ORDER BY id"),
        {"sid": scan_id},
    ).mappings().all()
    return [dict(r) for r in rows]

@app.get("/scans/{scan_id}/summary")
def scan_summary(scan_id: int, conn: Connection = Depends(get_conn)):
    key = f"scan:{scan_id}:summary"
    cached = cache.get_json(key)
    if cached is not None:
        return cached

    get_scan_or_404(conn, scan_id)
    rows = conn.execute(
        text(
            "SELECT resource_type, COUNT(*) AS n, "
            "COALESCE(SUM(monthly_cost_usd), 0) AS cost "
            "FROM resources WHERE scan_id = :sid GROUP BY resource_type"
        ),
        {"sid": scan_id},
    ).mappings().all()

    result = {
        "scan_id": scan_id,
        "resource_count": sum(r["n"] for r in rows),
        "total_monthly_cost_usd": float(sum(r["cost"] for r in rows)),
        "by_type": {r["resource_type"]: r["n"] for r in rows},
    }
    cache.set_json(key, result)
    return result

@app.get("/scans/{scan_id}/creation-order")
def get_creation_order(scan_id: int, conn: Connection = Depends(get_conn)):
    key = f"scan:{scan_id}:creation-order"
    cached = cache.get_json(key)
    if cached is not None:
        return cached

    get_scan_or_404(conn, scan_id)
    resources = conn.execute(
        text("SELECT id, resource_type, name FROM resources WHERE scan_id = :sid ORDER BY id"),
        {"sid": scan_id},
    ).mappings().all()
    edges = conn.execute(
        text(
            "SELECT from_resource_id, to_resource_id "
            "FROM resource_dependencies WHERE scan_id = :sid"
        ),
        {"sid": scan_id},
    ).all()

    try:
        order = creation_order(
            [r["id"] for r in resources], [(e[0], e[1]) for e in edges]
        )
    except CycleError as exc:
        logger.warning("cycle in scan %s: %s", scan_id, exc.stuck)
        raise HTTPException(status_code=409, detail=str(exc))

    by_id = {r["id"]: r for r in resources}
    result = [
        {
            "position": i + 1,
            "id": rid,
            "resource_type": by_id[rid]["resource_type"],
            "name": by_id[rid]["name"],
        }
        for i, rid in enumerate(order)
    ]
    cache.set_json(key, result)
    return result

@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

@app.get("/scans/{scan_id}/resources/{resource_id}/impact")
def resource_impact(scan_id: int, resource_id: int, conn: Connection = Depends(get_conn)):
    get_scan_or_404(conn, scan_id)
    resources = conn.execute(
        text("SELECT id, resource_type, name FROM resources WHERE scan_id = :sid"),
        {"sid": scan_id},
    ).mappings().all()
    by_id = {r["id"]: r for r in resources}
    if resource_id not in by_id:
        raise HTTPException(
            status_code=404, detail=f"Resource {resource_id} not found in scan {scan_id}"
        )
    edges = conn.execute(
        text(
            "SELECT from_resource_id, to_resource_id "
            "FROM resource_dependencies WHERE scan_id = :sid"
        ),
        {"sid": scan_id},
    ).all()

    affected = affected_by(resource_id, [(e[0], e[1]) for e in edges])
    return {
        "resource_id": resource_id,
        "name": by_id[resource_id]["name"],
        "affected_count": len(affected),
        "affected": [
            {"id": rid, "resource_type": by_id[rid]["resource_type"], "name": by_id[rid]["name"]}
            for rid in affected
        ],
    }