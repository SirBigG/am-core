# Registry variety publication API

`PATCH /api/registry/varieties/{variety_id}/publication/` links an existing
registry Variety to an existing Post. Use the Post ID returned by the Content
API and a Content API token issued to a staff user (`is_staff`).

```http
PATCH /api/registry/varieties/456/publication/
Authorization: Token <token-from-runtime-environment>
Content-Type: application/json

{"publication_id": 123}
```

| Status | Result |
| --- | --- |
| `200 OK` | Returns the stored pair `{"variety_id": 456, "publication_id": 123}` for both the initial write and an identical retry. |
| `400 Bad Request` | Supply `publication_id` as a positive JSON integer. A missing field or any other value, including `null`, is invalid. |
| `401 Unauthorized` | The token is missing or invalid. |
| `403 Forbidden` | The token belongs to a non-staff user. |
| `404 Not Found` | The variety or publication does not exist. |
| `409 Conflict` | A different publication is already linked. The response includes `code: "publication_conflict"`, `detail`, and the stored `variety_id` and `publication_id`. |

Concurrent requests for different publications leave the first committed link in
place. Use the IDs in the conflict response to reconcile the batch against the
existing link.
