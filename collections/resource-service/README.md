# Resource Postman demos

The normal HTTP collection targets Gateway on port 8000. Run it for CRUD,
gathering, consumption and transaction checks. World event POSTs no longer belong
in that collection: the Gateway rejects internal `/api/events/...` routes.

## Section-unlocked event over gRPC

Start the updated Resource image/source with Broker and Discovery first.

1. In Postman, create a **gRPC request** to `localhost:50050` (TLS off).
2. Import `../../services/resource-service/Api/Protos/broker.proto` as the service
   definition. Choose `broker.Broker / Publish`.
3. Paste the contents of `section-unlocked.grpc.json` into the message body.
   Protobuf JSON represents `bytes` as Base64, so the file already encodes the event.
4. Invoke it. `{"ok":true}` means the Broker accepted it, not that Resource has
   finished processing it. Verify first that `GET http://localhost:8500/api/registry/services/resource`
   lists instances with topic `section-unlocked`.
5. After delivery, use a normal GET:
   `http://localhost:8000/api/resource-nodes/lab4-grpc-node`.
   Expect quantity 0 and capacity 50.
6. Invoke the same gRPC message again. The node should remain unchanged and no
   dead letter should appear for this event at `http://localhost:8600/dead-letters`.

Alternatively, run `python3 scripts/demo_resource_event.py` from CPR. It publishes
through gRPC, polls the result through Gateway, and checks duplicate delivery.
Use its `--suffix` option for a fresh demo after deleting a previous demo node;
processed event IDs intentionally remain recorded even if the node is removed.

`section-unlocked.grpc.json` is a gRPC message example, not an importable HTTP
Postman collection. The protobuf definition is imported separately.
