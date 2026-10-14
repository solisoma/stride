from fastapi import HTTPException
from db.models import Journey, Ownership


def authorize(journey_id, db, user):
    owner = db.get(Ownership, journey_id)
    journey = db.get(Journey, journey_id)
    if not owner or owner.user_id != user.id or journey is None:
        raise HTTPException(404, "Journey not found")
    return journey
