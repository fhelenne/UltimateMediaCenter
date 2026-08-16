import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def _run(*args: str) -> bool:
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
    except OSError as exc:
        logger.error(f"ebook subprocess failed to start: {args[0]}: {exc}", extra={"cmd": args[0], "error": str(exc)})
        return False
    if process.returncode != 0:
        logger.error(
            f"ebook subprocess exited non-zero: {args[0]}",
            extra={"cmd": args[0], "returncode": process.returncode, "stderr": stderr.decode(errors="replace")},
        )
        return False
    return True


async def scan_and_enrich(path: str) -> None:
    if not await _run("calibredb", "add", "--library-path", settings.calibre_library_path, path):
        return
    await _run("fetch-ebook-metadata", path)
