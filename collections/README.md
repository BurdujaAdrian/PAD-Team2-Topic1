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

## Conventions

- Name files `<service-name>.postman_collection.json`.
- Use a `{{baseUrl}}` variable for the host; never commit credentials or tokens.
