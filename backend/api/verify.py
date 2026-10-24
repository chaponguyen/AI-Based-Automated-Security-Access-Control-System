# Agent 2
from fastapi import APIRouter
router = APIRouter(prefix="/api/verify", tags=["verify"])
# POST ""   multipart: image -> {user, similarity, liveness, decision, reason}
