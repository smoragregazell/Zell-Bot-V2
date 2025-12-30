import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

@router.get("/download-log/{logname}")
def download_log(logname: str, request: Request):
    # Check token in header
    token = request.headers.get("X-Admin-Token")
    expected_token = os.getenv("ADMIN_ACCESS_TOKEN")

    if not expected_token or token != expected_token:
        raise HTTPException(status_code=403, detail="🛑 Invalid or missing admin token.")

    file_path = os.path.join("logs", logname)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail=f"❓ Log file '{logname}' not found.")

    return FileResponse(
        path=file_path,
        media_type="text/plain",
        filename=logname
    )
