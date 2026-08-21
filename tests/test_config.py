from app.config import HOST_LIBRARY_ROOT, SHARES_MOUNT, Settings


def test_shares_mount_and_host_library_root_are_not_env_overridable(monkeypatch):
    """Regression test for finding C1: SHARES_MOUNT/HOST_LIBRARY_ROOT are host-side
    variables used only for docker-compose ${...} interpolation and install.sh. They
    must never be readable as pydantic Settings fields — pydantic-settings is
    case-insensitive, so a Settings field of the same name would be silently
    overwritten by the host value injected into the container's environment.

    They're plain module constants (not Settings fields), so instantiating Settings
    with SHARES_MOUNT/HOST_LIBRARY_ROOT set in the environment must have zero effect
    on them.
    """
    monkeypatch.setenv("SHARES_MOUNT", "/mnt/host-path")
    monkeypatch.setenv("HOST_LIBRARY_ROOT", "/home/someuser")

    instance = Settings()

    assert SHARES_MOUNT == "/library-root/shares"
    assert HOST_LIBRARY_ROOT == "/library-root"
    assert "shares_mount" not in Settings.model_fields
    assert "host_library_root" not in Settings.model_fields
    assert not hasattr(instance, "shares_mount")
    assert not hasattr(instance, "host_library_root")
