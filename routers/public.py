from fastapi import APIRouter

router = APIRouter()

@router.get("/info")
def get_info():
    return {"message": "Welcome to ProTown public API", "status": "ok"}
