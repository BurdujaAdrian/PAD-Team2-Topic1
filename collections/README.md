# Postman Collections

One subfolder per service. Each holds that service's Postman collection (v2.1) and, if needed, a local environment file.

```
collections/
├── base-service/
│   ├── base-service.postman_collection.json
│   └── base-service.local.postman_environment.json
├── crafting-service/
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

## Conventions

- Name files `<service-name>.postman_collection.json`.
- Use a `{{baseUrl}}` variable for the host; never commit credentials or tokens.
