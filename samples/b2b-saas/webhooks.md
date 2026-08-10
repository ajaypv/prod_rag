# NimbusFlow Webhook Delivery and Signatures

This is fictional test documentation for the prodRAG demo.

## Delivery requirements

Webhook endpoints must use HTTPS and return a `2xx` status within 10 seconds. Redirects are not
followed. NimbusFlow sends JSON with `Content-Type: application/json` and a unique event ID in
the `X-Nimbus-Event-Id` header.

When delivery fails, NimbusFlow retries after 1 minute, 5 minutes, 30 minutes, 2 hours, and 12
hours. The same event ID is reused. Consumers must store processed event IDs so a retry does not
apply the same business action twice.

## Signature verification

NimbusFlow signs the exact raw request body with HMAC-SHA256. The `X-Nimbus-Signature` header
contains the hexadecimal digest. Compute the digest before parsing or reformatting the JSON, then
compare signatures with a constant-time comparison. A proxy that changes whitespace or character
encoding can cause a signature mismatch.

The `X-Nimbus-Timestamp` value must be within five minutes of the receiver's current UTC time.
Reject older requests to reduce replay risk.

## Troubleshooting

For repeated `400` responses, confirm that the receiver reads the raw body, uses the current
webhook signing secret, and accepts the documented content type. Never paste the signing secret
into a ticket. Provide the event ID, UTC timestamp, endpoint host, and response status instead.
