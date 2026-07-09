"""Administrative reporting and export endpoints."""
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import cache
from ..auth import require_admin
from ..database import get_db
from ..errors import AppError
from ..models import Booking, Room, User
from ..services.export import generate_export

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/usage-report")
def usage_report(
    frm: str = Query(..., alias="from"),
    to: str = Query(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    cached = cache.get_report(admin.org_id, frm, to)
    if cached is not None:
        return cached

    try:
        from_date = datetime.strptime(frm, "%Y-%m-%d").date()
        to_date = datetime.strptime(to, "%Y-%m-%d").date()
    except ValueError:
        raise AppError(400, "INVALID_BOOKING_WINDOW", "Invalid date range")

    # Validate that the date range is valid
    if from_date > to_date:
        raise AppError(
            400,
            "INVALID_BOOKING_WINDOW",
            "'from' date must not be later than 'to' date",
        )

    range_start = datetime.combine(from_date, time.min)
    range_end = datetime.combine(to_date + timedelta(days=1), time.min)

    rooms = (
        db.query(Room)
        .filter(Room.org_id == admin.org_id)
        .order_by(Room.id.asc())
        .all()
    )

    room_ids = [room.id for room in rooms]

    if not room_ids:
        bookings_stats = []
    else:
        bookings_stats = (
            db.query(
                Booking.room_id,
                func.count(Booking.id).label("confirmed_bookings"),
                func.sum(Booking.price_cents).label("revenue_cents"),
            )
            .filter(
                Booking.room_id.in_(room_ids),
                Booking.status == "confirmed",
                Booking.start_time >= range_start,
                Booking.start_time < range_end,
            )
            .group_by(Booking.room_id)
            .all()
        )

    stats_by_room = {
        stat.room_id: {
            "confirmed_bookings": stat.confirmed_bookings,
            "revenue_cents": stat.revenue_cents or 0,
        }
        for stat in bookings_stats
    }

    room_rows = [
        {
            "room_id": room.id,
            "room_name": room.name,
            "confirmed_bookings": stats_by_room.get(room.id, {}).get("confirmed_bookings", 0),
            "revenue_cents": stats_by_room.get(room.id, {}).get("revenue_cents", 0),
        }
        for room in rooms
    ]

    result = {
        "from": frm,
        "to": to,
        "rooms": room_rows,
    }

    cache.set_report(admin.org_id, frm, to, result)

    return result


@router.get("/export")
def export(
    room_id: int | None = Query(None),
    include_all: bool = Query(False),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    csv_body = generate_export(
        db,
        admin.org_id,
        admin.id,
        room_id,
        include_all,
    )

    return Response(
        content=csv_body,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=export.csv"},
    )
