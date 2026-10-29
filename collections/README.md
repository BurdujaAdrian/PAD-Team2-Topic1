# Postman Collections

One subfolder per service. Each holds that service's Postman collection (v2.1) and, if needed, a local environment file.

```
collections/
├── base-service/
│   ├── base-service.postman_collection.json
│   └── base-service.local.postman_environment.json
├── crafting-service/
├── discovery-service/
├── exam-service/
├── game-service/
├── player-service/
├── resource-service/
├── world-service/
└── zombie-service/
```

## Import

In Postman (or the VS Code extension): **Import** → select the `*.postman_collection.json` file, and the `*.postman_environment.json` file if there is one. Select the environment in the top-right before sending requests.

## Run from the terminal

```
npx newman run collections/base-service/base-service.postman_collection.json -e collections/base-service/base-service.local.postman_environment.json
```

## Base, Crafting and Discovery

Base and Crafting run as several replicas without a port of their own, so their collections send every request to the Gateway (`baseUrl` = `http://localhost:8000`), which balances them among the instances registered in Discovery. The whole stack has to be running (`docker compose up -d` in the CPR). Each collection starts with a **Discovery** folder that checks the instances are registered (`discoveryUrl` = `http://localhost:8500`).

The Discovery collection checks the registry itself and walks a made-up instance through register, refresh, conflict and deregister. To see which instance answered each request, follow `docker logs -f cpr-gateway`.

## Exam and World

Exam and World also run as two replicas without a port of their own, so their collections and environments point at the Gateway (`baseUrl` = `http://localhost:8000`). Both replicas share one database, so a run that creates something through one replica and reads it through the other still passes.

Each collection ends with a **Lab 3 – replicas** folder (`discoveryUrl` = `http://localhost:8500`): it checks that Discovery lists at least two healthy replicas with their load, then sends the same request twice and checks that `X-Service-Instance` names a different replica each time (Round-Robin). The folder before it, **Status at baseUrl**, answers with the Gateway's own status when run through the Gateway; a replica's status is what Discovery reports.

```bash
npx newman run collections/exam-service/exam-service.postman_collection.json \
  -e collections/exam-service/exam-service.local.postman_environment.json
```

## Conventions

- Name files `<service-name>.postman_collection.json`.
- Use a `{{baseUrl}}` variable for the host; never commit credentials or tokens.
