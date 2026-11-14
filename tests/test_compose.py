from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_compose_uses_only_bind_mounts():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    assert "volumes" not in compose, "Top-Level Named Volumes sind verboten."
    for service_name, service in compose["services"].items():
        for volume in service.get("volumes", []):
            assert isinstance(volume, str), f"{service_name}: Named Volume {volume!r}"
            source = volume.split(":", 1)[0]
            assert source.startswith("./") or source in {"/etc/passwd", "/etc/group"}, (
                f"{service_name}: kein Bind-Mount: {volume}"
            )


def test_docker_data_directories_exist():
    for path in [
        "postgres",
        "redis",
        "static",
        "media",
        "logs",
        "playwright_profiles",
    ]:
        assert (ROOT / "docker-data" / path).exists(), path


def test_required_services_present():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    for service in ["web", "db", "redis", "celery_worker", "celery_beat", "node_builder"]:
        assert service in compose["services"]
