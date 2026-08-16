from unittest.mock import AsyncMock, patch

from app.ebooks.ebooks import scan_and_enrich


def _mock_process(returncode: int = 0):
    process = AsyncMock()
    process.communicate = AsyncMock(return_value=(b"", b""))
    process.returncode = returncode
    return process


async def test_success_runs_calibredb_then_fetch_metadata():
    calls = []

    async def _fake_exec(*args, **kwargs):
        calls.append(args)
        return _mock_process(0)

    with patch("asyncio.create_subprocess_exec", side_effect=_fake_exec):
        await scan_and_enrich("/test/library/incoming/Dune.epub")

    assert len(calls) == 2
    assert calls[0][0] == "calibredb"
    assert "add" in calls[0]
    assert "--library-path" in calls[0]
    assert "/test/library" in calls[0]
    assert "/test/library/incoming/Dune.epub" in calls[0]
    assert calls[1][0] == "fetch-ebook-metadata"
    assert "/test/library/incoming/Dune.epub" in calls[1]


async def test_calibredb_failure_is_logged_not_raised(caplog):
    async def _fake_exec(*args, **kwargs):
        return _mock_process(1)

    with patch("asyncio.create_subprocess_exec", side_effect=_fake_exec):
        await scan_and_enrich("/test/library/incoming/Dune.epub")

    assert "calibredb" in caplog.text.lower()


async def test_fetch_metadata_failure_is_logged_not_raised(caplog):
    call_count = 0

    async def _fake_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _mock_process(0 if call_count == 1 else 1)

    with patch("asyncio.create_subprocess_exec", side_effect=_fake_exec):
        await scan_and_enrich("/test/library/incoming/Dune.epub")

    assert "fetch-ebook-metadata" in caplog.text.lower()


async def test_subprocess_oserror_is_logged_not_raised(caplog):
    async def _fake_exec(*args, **kwargs):
        raise OSError("calibredb not found")

    with patch("asyncio.create_subprocess_exec", side_effect=_fake_exec):
        await scan_and_enrich("/test/library/incoming/Dune.epub")

    assert "calibredb not found" in caplog.text
