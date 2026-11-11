"""Isolated Lab 4 smoke test; requires Docker and locally built shared images.

Run from CPR: python3 scripts/verify_lab4.py
Uses unique project/volumes and free loopback ports. Always removes only its own
containers and volumes. Does not start the team's normal stack or send Telegram.
"""

import io
import json
import os
import secrets
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKER = os.environ.get("DOCKER", "docker")
PROJECT = "pad-lab4-check-" + secrets.token_hex(4)


def run(*args, **kwargs):
    return subprocess.run(
        [DOCKER, *args], check=True, text=True, capture_output=True, **kwargs
    ).stdout


def port(kind=socket.SOCK_STREAM):
    with socket.socket(socket.AF_INET, kind) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def http(base, path, method="GET", body=None, headers=None):
    headers = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        base + path, data=data, method=method, headers=headers
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def eventually(check, seconds=120):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except (OSError, ValueError, AssertionError) as error:
            last = error
        time.sleep(1)
    raise AssertionError(f"Timed out waiting for check: {last}")


def main():
    config = json.loads(
        run(
            "compose",
            "--env-file",
            str(ROOT / ".env.example"),
            "-f",
            str(ROOT / "docker-compose.yml"),
            "config",
            "--format",
            "json",
        )
    )
    selected = {
        "gateway",
        "broker",
        "discovery",
        "zombie-api",
        "resource-api",
        "zombie-db",
        "resource-db",
    }
    config["services"] = {k: v for k, v in config["services"].items() if k in selected}
    config.pop("name", None)
    config.pop("networks", None)
    config["volumes"] = {
        name: {} for name in ["broker_data", "zombie_pgdata", "resource_pgdata"]
    }
    ports = {name: port() for name in ["gateway", "broker", "discovery"]}
    syslog_port = port(socket.SOCK_DGRAM)
    token = secrets.token_hex(24)
    for name, service in config["services"].items():
        service.pop("container_name", None)
        service.pop("networks", None)
        service.pop("ports", None)
        service["logging"]["options"]["syslog-address"] = (
            f"udp://127.0.0.1:{syslog_port}"
        )
        if name in ports:
            service["ports"] = [f"127.0.0.1:{ports[name]}:8080"]
        if name == "broker":
            service["ports"].append(f"127.0.0.1:{syslog_port}:5514/udp")
            service["environment"]["LOG_DOWNLOAD_TOKEN"] = token
            # Keep a known replica cached while it is paused, so three actual
            # failed calls test the Broker breaker rather than health exclusion.
            service["environment"]["DISCOVERY_REFRESH_SECONDS"] = "60"
            service["environment"]["TASK_TIMEOUT_SECONDS"] = "1"
        if name == "discovery":
            service["environment"]["TELEGRAM_BOT_TOKEN"] = ""
            service["environment"]["TELEGRAM_CHAT_ID"] = ""
    gateway, broker, discovery = [
        f"http://127.0.0.1:{ports[n]}" for n in ["gateway", "broker", "discovery"]
    ]
    with tempfile.TemporaryDirectory(prefix="pad-lab4-") as tmp:
        compose = Path(tmp) / "compose.json"
        compose.write_text(json.dumps(config))
        command = ["compose", "-p", PROJECT, "-f", str(compose)]
        try:
            print("Starting isolated nine-container stack", flush=True)
            run(*command, "up", "-d", "--wait", "--wait-timeout", "180")
            for base in [gateway, broker, discovery]:
                eventually(lambda base=base: http(base, "/api/status")[0] == 200)
            for name in ["zombie", "resource"]:

                def registered(name=name):
                    data = json.loads(
                        http(discovery, f"/api/registry/services/{name}")[2]
                    )
                    return len(data["instances"]) == 2

                eventually(registered)
            print("PASS: health and two replicas per service", flush=True)
            for path in ["/api/zombies/types", "/api/resource-nodes"]:
                status, headers, _ = http(gateway, path)
                assert status == 200, status
                assert any(k.lower() == "x-service-instance" for k in headers), headers
            zombie = {
                "name": "Lab4 test",
                "category": "tourist",
                "health": 80,
                "speed": 2.1,
                "attack_strength": 12,
                "perception_radius": 10,
                "abilities": ["sprint"],
            }
            status, _, body = http(gateway, "/api/zombies/types", "POST", zombie)
            assert status == 201, (status, body)
            for _ in range(6):
                assert b"Lab4 test" in http(gateway, "/api/zombies/types")[2]
            # Old service callers can address the Broker directly without the Gateway.
            assert http(broker, "/api/resource-nodes")[0] == 200
            print(
                "PASS: real business reads/writes and internal Broker compatibility",
                flush=True,
            )
            registration = {
                "service": "lab4-demo",
                "instance_id": "lab4-demo",
                "address": "http://broker:8080",
                "topics": ["lab4-demo"],
            }
            assert (
                http(discovery, "/api/registry/instances", "POST", registration)[0]
                == 201
            )
            assert "lab4-demo" in json.loads(http(broker, "/topics")[2])
            assert (
                http(discovery, "/api/registry/instances/lab4-demo", "DELETE")[0] == 204
            )
            print("PASS: Discovery topic registration visible to Broker", flush=True)
            assert http(broker, "/logs")[0] == 401

            def archive_ready():
                status, _, data = http(broker, "/logs", headers={"X-Log-Token": token})
                assert status == 200
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    logs = b"\n".join(archive.read(n) for n in archive.namelist())
                return all(
                    name in logs
                    for name in [
                        b"zombie-api",
                        b"resource-api",
                        b"gateway",
                        b"discovery",
                    ]
                )

            eventually(archive_ready, seconds=30)
            print(
                "PASS: authenticated system log ZIP includes all tested services",
                flush=True,
            )
            zombie_ids = run(*command, "ps", "-q", "zombie-api").split()
            paused = zombie_ids[0]
            instance_id = run(
                "inspect", "--format", "{{.Config.Hostname}}", paused
            ).strip()
            run("pause", paused)
            try:
                for _ in range(3):
                    result = http(
                        broker,
                        "/send/zombie/api/zombies/types",
                        headers={"X-Instance-Id": instance_id},
                    )
                    assert result[0] == 504, result[0]
                removed = json.loads(http(broker, "/routing")[2])["circuit_breaker"][
                    "removed"
                ]
                assert removed, removed
                for _ in range(3):
                    status, headers, _ = http(gateway, "/api/zombies/types")
                    assert status == 200
                    assert (
                        next(
                            v
                            for k, v in headers.items()
                            if k.lower() == "x-service-instance"
                        )
                        != instance_id
                    )
                print(
                    "PASS: three real timeouts trip Broker breaker; Gateway uses surviving replica",
                    flush=True,
                )
            finally:
                run("unpause", paused)
            # Queue survives process/container restart (test entry uses a service
            # with no instances, so it is retained in queue/dead letters).
            broker_id = run(*command, "ps", "-q", "broker").strip()
            run(
                "exec",
                broker_id,
                "python",
                "-c",
                "import store; store.enqueue('restart-check','missing','demo',b'{}')",
            )
            run(*command, "restart", "broker")
            eventually(lambda: http(broker, "/api/status")[0] == 200)
            count = run(
                "exec",
                broker_id,
                "python",
                "-c",
                "import store; print(store.run(\"SELECT count(*) FROM queue WHERE id='restart-check'\")[0][0]+store.run(\"SELECT count(*) FROM dead WHERE id='restart-check'\")[0][0])",
            )
            assert count.strip() == "1", count
            assert http(gateway, "/api/zombies/types")[0] == 200
            print(
                "PASS: Broker restart retains queued/dead-letter message and routing recovers",
                flush=True,
            )
            print("ALL LIVE CHECKS PASSED", flush=True)
        finally:
            run(*command, "down", "--volumes", "--remove-orphans")
            print("Removed isolated test containers and disposable volumes", flush=True)


if __name__ == "__main__":
    main()
