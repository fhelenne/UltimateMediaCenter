import httpx
import pytest
import respx

from app.library import rootfolder


@pytest.mark.parametrize(
    "arr,base_url,api_version",
    [
        ("sonarr", "http://sonarr-test:8989", "v3"),
        ("radarr", "http://radarr-test:7878", "v3"),
        ("lidarr", "http://lidarr-test:8686", "v1"),
        ("readarr", "http://readarr-test:8787", "v1"),
    ],
)
@respx.mock
async def test_add_root_folder_returns_id(arr, base_url, api_version):
    respx.post(f"{base_url}/api/{api_version}/rootfolder").mock(
        return_value=httpx.Response(201, json={"id": 7, "path": "/library-root/x"})
    )
    result = await rootfolder.add_root_folder(arr, "/library-root/x")
    assert result == "7"


@respx.mock
async def test_add_root_folder_returns_none_on_http_error():
    respx.post("http://sonarr-test:8989/api/v3/rootfolder").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    result = await rootfolder.add_root_folder("sonarr", "/library-root/x")
    assert result is None


@respx.mock
async def test_remove_root_folder_true_on_success():
    respx.delete("http://sonarr-test:8989/api/v3/rootfolder/7").mock(
        return_value=httpx.Response(200)
    )
    result = await rootfolder.remove_root_folder("sonarr", "7")
    assert result is True


@respx.mock
async def test_remove_root_folder_false_on_http_error():
    respx.delete("http://lidarr-test:8686/api/v1/rootfolder/3").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    result = await rootfolder.remove_root_folder("lidarr", "3")
    assert result is False
