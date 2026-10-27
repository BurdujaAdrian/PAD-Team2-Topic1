# Zombie and Resource: local Lab 3 checks

Run from the CPR root with Docker Desktop running:

```sh
docker compose -f docker-compose.zombie-resource-lab3.yml up -d --build
docker compose -f docker-compose.zombie-resource-lab3.yml ps
```

This builds the local Discovery, gateway, Zombie and Resource sources. Each business service has two API replicas sharing its own PostgreSQL database. The databases use separate volumes from the shared stack, an example local password, and no published database ports. The shared deployment compose file still uses the published images.

The service changes must be committed in their individual repositories before updating the CPR submodule references. The gateway checkout must include its Discovery instance pool.

## Presentation checks

1. Open `http://localhost:18500/api/registry/services/zombie` and `/api/registry/services/resource`. Each should contain two distinct instance IDs and addresses.
2. Set the Postman gateway URL to `http://localhost:18000`. Repeated requests to `/api/zombies/types` or `/api/resource-nodes` should alternate the `X-Service-Instance` response header. The gateway's `/api/status` describes the gateway; each registered instance exposes its own `/api/status` internally with database health and load.
3. Create data through one replica and read it through the other. Both use the same service database. Mutation locks and persisted operation IDs protect supported duplicate operations across replicas.
4. Restart Discovery and check that the services register again:

```sh
docker compose -f docker-compose.zombie-resource-lab3.yml restart discovery
```

Registrations refresh every two seconds in this setup; the gateway refreshes its registry cache every second.

5. Scale Zombie down and back up, checking the registry and response headers after each change:

```sh
docker compose -f docker-compose.zombie-resource-lab3.yml up -d --scale zombie-api=1
docker compose -f docker-compose.zombie-resource-lab3.yml up -d --scale zombie-api=2
docker compose -f docker-compose.zombie-resource-lab3.yml logs --tail=50 zombie-api resource-api
```

Graceful shutdown deregisters the stopped instance. Discovery now polls health and reports a crash as unhealthy, but automatic routing removal is still pending. A saturated API can return HTTP 429 even for a health probe; monitoring reports this as overload. Notification delivery is also still pending.

Stop this stack while retaining its database data:

```sh
docker compose -f docker-compose.zombie-resource-lab3.yml down
```

Do not add `-v` unless you intend to erase these local test databases.

## Verified locally (2026-10-27)

- Each service passed 22 request-control/PostgreSQL checks plus registration lifecycle and load-counter checks.
- All four source images built on the local ARM64 Docker engine. Both replicas of each API started against fresh databases and completed migrations.
- Discovery listed two healthy, individually reachable instances per service; six consecutive gateway requests alternated instance headers.
- A Zombie created through one replica was read through the other. A repeated Resource gather action reached the other replica, returned 409, and reduced stock only once.
- Restarting Discovery rebuilt its registry through registration refreshes.
- Scaling each service from two replicas to one removed the stopped instance from the registry and gateway rotation; restoring two replicas restored alternating requests.

These checks cover the local source build, not a published release or the full team's deployment.

## Grades 7 and 8

Gateway forwarding, Gateway Discovery lookups, Zombie/Resource Discovery calls
and Discovery health probes now track failures per downstream instance. Three
errors inside the relevant outbound timeout × 3.5 log `circuit_breaker_tripped`.
This is grade 7 observation-only behaviour: requests continue; no automatic
removal or retry is added. Ordinary client errors do not count; HTTP 429, HTTP 5xx,
timeouts and connection failures do. Cancelled callers are not counted.

Discovery polls every second in this demonstration setup, with a two-second probe
timeout. It logs `load_critical` at 80% capacity (or on HTTP 429),
`health_check_failed` for unsuccessful checks, and `instance_recovered` on recovery.
Repeated alerts have a 30-second cooldown. Registry responses include
`health_status`, `last_checked_at` and `load`, so the existing Postman registration
requests also show the monitoring results. Routing `state` remains unchanged:
grade 10 exclusion and grade 9 notifications are still pending.

Watch logs from the CPR root:

```sh
docker compose -f docker-compose.zombie-resource-lab3.yml logs -f --tail=30 gateway discovery zombie-api resource-api
```

The Gateway uses `feature/lab3-circuit-breaker`; Discovery uses
`feature/lab3-health-monitoring`. Zombie and Resource changes remain on their
existing `feature/lab3-discovery` branches. No images are published until the
individual repository release workflows run after approved merges.

Other teammates' services still need the grade 7 tracker on their own outgoing
calls; this implementation does not add it automatically to those repositories.

### Grade 7/8 validation

- Gateway's suite passed 106 tests; Discovery's suite covers monitor concurrency,
  polling, shutdown, timeouts, malformed load, cooldowns and recovery.
- Both C# suites passed the PostgreSQL checks and breaker checks, including
  response-body timeouts and excluding caller cancellation.
- Pausing one Zombie replica produced gateway timeouts and a breaker-trip log
  while healthy-replica requests succeeded. Discovery logged health failures and
  recovery after unpausing it.
- Stopping Discovery produced breaker-trip logs in Zombie and Resource;
  restarting it restored registration and healthy probe results.
- A temporary HTTP test instance reporting 9/10 active tasks produced a
  `load_critical` log. Reporting 0/10 restored healthy status. The temporary
  instance and container were removed after verification.

## Coverage verification (2026-10-27)

All four service CI workflows now enforce at least 80% **application line
coverage** and upload reports. The C# coverage scripts were also exercised inside
Linux .NET 8 containers against disposable PostgreSQL databases.

| Service | Line coverage |
| --- | --- |
| Zombie | 82.71% |
| Resource | 83.82% |
| Gateway | 98.43% |
| Discovery | 96.21% |

C# coverage includes the application assembly without manual file exclusions;
Python coverage includes `app`. Tests and dependencies are not counted. Branch
coverage is not the gate. The new business tests verify CRUD persistence,
validation, duplicate transactions, atomic consumption and World-event rollback.
No runtime business behaviour was changed to raise coverage.

Run `bash scripts/coverage.sh` from either C# repository with
`TEST_DATABASE_CONNECTION` set; the script refuses to skip database checks.
The Python command is documented in each shared service's README. GitHub Actions
will run these checks after the branches are pushed and PRs are opened.
