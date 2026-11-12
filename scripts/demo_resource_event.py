"""Publish a real Broker gRPC event and verify Resource delivery and duplicates.
Run from CPR: python3 scripts/demo_resource_event.py [--suffix demo2]
Requires the running Compose broker, Gateway and updated Resource replicas.
"""

import argparse
import json
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suffix", default="grpc")
    parser.add_argument("--gateway", default="http://localhost:8000")
    parser.add_argument("--broker", default="http://localhost:8600")
    parser.add_argument("--discovery", default="http://localhost:8500")
    args = parser.parse_args()
    if not args.suffix or not all(c.isalnum() or c in "-_" for c in args.suffix):
        parser.error("suffix must contain only letters, digits, hyphens or underscores")
    prefix = "lab4-" + args.suffix
    node = prefix + "-node"
    with urllib.request.urlopen(
        args.discovery + "/api/registry/services/resource", timeout=5
    ) as response:
        instances = json.load(response)["instances"]
    if not any("section-unlocked" in i.get("topics", []) for i in instances):
        raise SystemExit(
            "Resource has no section-unlocked subscription; start its Lab 4 version first."
        )
    event = {
        "event_id": prefix + "-event",
        "world_id": "lab4-world",
        "section_id": "lab4-section",
        "trigger_id": prefix + "-trigger",
        "rooms": [{"room_id": "lab4-room", "type": "laboratory"}],
        "resource_nodes": [
            {"node_id": node, "room_id": "lab4-room", "resource_type": "metal"}
        ],
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    code = "import sys,grpc,broker_pb2 as pb,broker_pb2_grpc as rpc; c=grpc.insecure_channel('localhost:50050'); a=rpc.BrokerStub(c).Publish(pb.Event(topic='section-unlocked',payload=sys.stdin.buffer.read()),timeout=5); assert a.ok; print('Broker accepted event')"
    for attempt in range(2):
        subprocess.run(
            ["docker", "compose", "exec", "-T", "broker", "python", "-c", code],
            input=json.dumps(event).encode(),
            check=True,
            cwd=Path(__file__).resolve().parents[1],
        )
        # The publish Ack means queued, not processed. Wait for the Broker's
        # delivery loop to drain before claiming the duplicate has been handled.
        time.sleep(1.2)
        queue_deadline = time.monotonic() + 20
        while True:
            with urllib.request.urlopen(
                args.broker + "/metrics/", timeout=5
            ) as response:
                metrics = response.read().decode()
            value = next(
                (
                    float(line.split()[1])
                    for line in metrics.splitlines()
                    if line.startswith("broker_queue_size ")
                ),
                None,
            )
            if value == 0:
                break
            if time.monotonic() > queue_deadline:
                raise SystemExit(
                    "Broker queue has not drained; inspect pending events before repeating the demo."
                )
            time.sleep(1)
        with urllib.request.urlopen(
            args.broker + "/dead-letters", timeout=5
        ) as response:
            dead = json.load(response)
        if any(event["event_id"] in item["payload"] for item in dead):
            raise SystemExit("The demo event was dead-lettered; inspect Resource logs.")
        deadline = time.monotonic() + 20
        while True:
            try:
                with urllib.request.urlopen(
                    args.gateway + "/api/resource-nodes/" + node, timeout=5
                ) as response:
                    result = json.load(response)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.5)
        print(
            "First delivery" if attempt == 0 else "Duplicate delivery",
            json.dumps(result),
        )
    print("Inspect in Postman: " + args.gateway + "/api/resource-nodes/" + node)
    print(
        "A repeated event is acknowledged without resetting or creating its node again."
    )


if __name__ == "__main__":
    main()
