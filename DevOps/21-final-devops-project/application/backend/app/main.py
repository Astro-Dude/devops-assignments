import socket
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Comment, Ticket
from .observability import (
    HTTP_LATENCY,
    HTTP_REQUESTS,
    TICKETS_CREATED,
    configure_logging,
    register_collectors,
)
from .schemas import (
    CommentCreate,
    CommentOut,
    Priority,
    StatsOut,
    Status,
    TicketCreate,
    TicketOut,
    TicketUpdate,
)

log = configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    register_collectors()
    log.info("TicketHub API starting", extra={"extra_fields": {"host": socket.gethostname()}})
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)


@app.middleware("http")
async def observe(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    route = request.scope.get("route")
    route_path = getattr(route, "path", "unmatched")
    HTTP_REQUESTS.labels(request.method, route_path, str(response.status_code)).inc()
    HTTP_LATENCY.labels(request.method, route_path).observe(elapsed)
    if route_path not in ("/health", "/ready", "/metrics"):
        log.info(
            "request",
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round(elapsed * 1000, 2),
                }
            },
        )
    return response


# ---------------------------------------------------------------- platform endpoints
@app.get("/")
def root():
    return {"service": settings.app_name, "version": settings.app_version, "docs": "/docs"}


@app.get("/health")
def health():
    """Liveness: the process is up and the event loop answers."""
    return {"status": "UP"}


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    """Readiness: we can actually serve traffic (database reachable, schema present)."""
    try:
        db.execute(text("SELECT 1 FROM tickets LIMIT 1"))
    except Exception as exc:
        log.warning("readiness check failed", extra={"extra_fields": {"error": str(exc)[:200]}})
        raise HTTPException(status_code=503, detail="database not ready") from exc
    return {"status": "READY"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/info")
def info():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "pod": socket.gethostname(),
        "default_team": settings.default_team,
    }


# ---------------------------------------------------------------- tickets
def _get_ticket(db: Session, ticket_id: int) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.get("/api/tickets", response_model=list[TicketOut])
def list_tickets(
    status_filter: Status | None = Query(default=None, alias="status"),
    priority: Priority | None = None,
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
):
    stmt = select(Ticket).order_by(Ticket.id.desc())
    if status_filter:
        stmt = stmt.where(Ticket.status == status_filter)
    if priority:
        stmt = stmt.where(Ticket.priority == priority)
    if q:
        stmt = stmt.where(Ticket.subject.ilike(f"%{q}%"))
    return list(db.scalars(stmt))


@app.get("/api/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)):
    rows = db.execute(select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)).all()
    counts = dict(rows)
    urgent_open = db.scalar(
        select(func.count(Ticket.id)).where(
            Ticket.priority == "URGENT", Ticket.status.in_(["OPEN", "IN_PROGRESS"])
        )
    )
    return StatsOut(
        total=sum(counts.values()),
        open=counts.get("OPEN", 0),
        in_progress=counts.get("IN_PROGRESS", 0),
        resolved=counts.get("RESOLVED", 0),
        closed=counts.get("CLOSED", 0),
        urgent_open=urgent_open or 0,
    )


@app.get("/api/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    return _get_ticket(db, ticket_id)


@app.post("/api/tickets", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["team"] = data.get("team") or settings.default_team
    ticket = Ticket(**data, status="OPEN")
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    TICKETS_CREATED.labels(ticket.priority, ticket.category).inc()
    log.info("ticket created", extra={"extra_fields": {"ticket_id": ticket.id, "priority": ticket.priority}})
    return ticket


@app.put("/api/tickets/{ticket_id}", response_model=TicketOut)
def update_ticket(ticket_id: int, payload: TicketUpdate, db: Session = Depends(get_db)):
    ticket = _get_ticket(db, ticket_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(ticket, key, value)
    db.commit()
    db.refresh(ticket)
    return ticket


@app.delete("/api/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = _get_ticket(db, ticket_id)
    db.delete(ticket)
    db.commit()


# ---------------------------------------------------------------- comments
@app.get("/api/tickets/{ticket_id}/comments", response_model=list[CommentOut])
def list_comments(ticket_id: int, db: Session = Depends(get_db)):
    return _get_ticket(db, ticket_id).comments


@app.post(
    "/api/tickets/{ticket_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(ticket_id: int, payload: CommentCreate, db: Session = Depends(get_db)):
    ticket = _get_ticket(db, ticket_id)
    comment = Comment(ticket_id=ticket.id, **payload.model_dump())
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment
