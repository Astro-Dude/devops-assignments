"""Prometheus metrics and structured (JSON) logging for TicketHub."""

import json
import logging
import sys
import time

from prometheus_client import Counter, Histogram
from prometheus_client.core import REGISTRY, GaugeMetricFamily
from sqlalchemy import func, select

from .config import settings

HTTP_REQUESTS = Counter(
    "tickethub_http_requests_total",
    "HTTP requests handled by the API",
    ["method", "route", "status"],
)
HTTP_LATENCY = Histogram(
    "tickethub_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
TICKETS_CREATED = Counter(
    "tickethub_tickets_created_total",
    "Tickets created through the API",
    ["priority", "category"],
)


class TicketBacklogCollector:
    """Exposes the live ticket backlog from the database at scrape time.

    Business metrics like this are what the TicketHubUrgentBacklog alert uses.
    """

    def collect(self):
        from .db import SessionLocal
        from .models import Ticket

        gauge = GaugeMetricFamily(
            "tickethub_tickets_open", "Tickets not yet resolved/closed", labels=["priority"]
        )
        try:
            with SessionLocal() as db:
                rows = db.execute(
                    select(Ticket.priority, func.count(Ticket.id))
                    .where(Ticket.status.in_(["OPEN", "IN_PROGRESS"]))
                    .group_by(Ticket.priority)
                ).all()
            counts = dict(rows)
        except Exception:  # noqa: BLE001 - metrics must never break the scrape
            counts = {}
        for priority in ("LOW", "MEDIUM", "HIGH", "URGENT"):
            gauge.add_metric([priority], counts.get(priority, 0))
        yield gauge


_collector_registered = False


def register_collectors() -> None:
    global _collector_registered
    if not _collector_registered:
        REGISTRY.register(TicketBacklogCollector())
        _collector_registered = True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "env": settings.app_env,
            "version": settings.app_version,
        }
        payload.update(getattr(record, "extra_fields", {}))
        return json.dumps(payload)


def configure_logging() -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("tickethub")
    logger.handlers = [handler]
    logger.setLevel(settings.log_level.upper())
    logger.propagate = False
    return logger
