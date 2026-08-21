import httpx
import pytest
import respx

from app.library import rootfolder


@pytest.mark.parametrize(
    "arr,base_url,api_version",
    [
        ("sonarr", "http://sonarr-test:8989", "v3"),
        ("radarr", "http://radarr-test:7878", "v3"),
    ],
)
@respx.mock
async def test_add_root_folder_returns_id(arr, base_url, api_version):
    respx.post(f"{base_url}/api/{api_version}/rootfolder").mock(
        return_value=httpx.Response(201, json={"id": 7, "path": "/library-root/x"})
    )
    result = await rootfolder.add_root_folder(arr, "/library-root/x")
    assert result == "7"


@pytest.mark.parametrize(
    "arr,base_url",
    [
        ("lidarr", "http://lidarr-test:8686"),
        ("readarr", "http://readarr-test:8787"),
    ],
)
@respx.mock
async def test_add_root_folder_includes_default_profiles_for_v1_arrs(arr, base_url):
    """Regression test: lidarr/readarr's rootfolder endpoint (unlike
    sonarr/radarr) requires Name + a non-zero DefaultMetadataProfileId +
    DefaultQualityProfileId, or it 400s. add_root_folder must fetch the
    first available profile of each kind and include them."""
    respx.get(f"{base_url}/api/v1/metadataprofile").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "name": "Standard"}, {"id": 2, "name": "None"}])
    )
    respx.get(f"{base_url}/api/v1/qualityprofile").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "name": "eBook"}, {"id": 2, "name": "Spoken"}])
    )
    post_route = respx.post(f"{base_url}/api/v1/rootfolder").mock(
        return_value=httpx.Response(201, json={"id": 7, "path": "/books-library"})
    )
    result = await rootfolder.add_root_folder(arr, "/books-library")
    assert result == "7"
    sent = post_route.calls.last.request.content
    import json as _json

    body = _json.loads(sent)
    assert body["path"] == "/books-library"
    assert body["name"]
    assert body["defaultMetadataProfileId"] == 1
    assert body["defaultQualityProfileId"] == 1


@respx.mock
async def test_add_root_folder_v1_returns_none_when_no_profiles_exist():
    respx.get("http://readarr-test:8787/api/v1/metadataprofile").mock(
        return_value=httpx.Response(200, json=[])
    )
    result = await rootfolder.add_root_folder("readarr", "/books-library")
    assert result is None


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


@respx.mock
async def test_browse_returns_directory_list():
    respx.get("http://readarr-test:8787/api/v1/filesystem", params={"path": "/"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "directories": [
                    {"path": "/books-library/", "name": "books-library"},
                    {"path": "/library-root/", "name": "library-root"},
                ],
                "files": [{"path": "/config.xml", "name": "config.xml"}],
            },
        )
    )
    result = await rootfolder.browse("readarr", "/")
    assert result == [
        {"path": "/books-library/", "name": "books-library"},
        {"path": "/library-root/", "name": "library-root"},
    ]


@respx.mock
async def test_browse_returns_none_on_http_error():
    respx.get("http://sonarr-test:8989/api/v3/filesystem", params={"path": "/"}).mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    result = await rootfolder.browse("sonarr", "/")
    assert result is None
