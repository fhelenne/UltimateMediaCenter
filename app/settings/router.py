import asyncio
import json
import os

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse, Response

from app.auth.router import require_login
from app.config import settings
from app.settings import export_import

router = APIRouter()


@router.get("/settings/export")
async def export_config(user: dict = Depends(require_login)) -> Response:
    data = export_import.build_export(settings.db_path)
    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=umc-config-export.json"},
    )


@router.post("/settings/import")
async def import_config(
    user: dict = Depends(require_login), file: UploadFile = File(...)
) -> JSONResponse:
    raw = await file.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return JSONResponse({"errors": ["fichier JSON invalide"]}, status_code=400)

    result = await export_import.apply_import(settings.db_path, data)
    if result["errors"] and not result["env_written"]:
        return JSONResponse(result, status_code=400)

    response = JSONResponse(result)

    # Différer l'arrêt d'une seconde pour laisser la réponse HTTP partir
    # avant que le process ne s'arrête ; restart: unless-stopped relance
    # le container avec le nouvel .env.
    asyncio.get_event_loop().call_later(1, lambda: os._exit(0))
    return response
