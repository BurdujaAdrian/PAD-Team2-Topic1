# Secrets

The real credential files live here and are git-ignored. Only the `*.example.json`
templates are committed.

rqlite reads its users from a JSON file rather than from environment variables,
which is why the Exam and World services need one here while the Postgres-backed
services get theirs from `.env`.

## Setting it up

```bash
cp secrets/exam-rqlite-users.example.json  secrets/exam-rqlite-users.json
cp secrets/world-rqlite-users.example.json secrets/world-rqlite-users.json
```

Replace every `REPLACE_ME` with a username and password of your choosing, then
put the same pair in `EXAM_RQLITE_USER` / `EXAM_RQLITE_PASSWORD` and
`WORLD_RQLITE_USER` / `WORLD_RQLITE_PASSWORD` in your `.env`. The two have to
match: the file is what rqlite accepts, and `.env` is what the service sends.

The anonymous `"*"` entry keeps `status` and `ready` readable without
credentials, which is what the container health check uses.
