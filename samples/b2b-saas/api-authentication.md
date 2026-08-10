# NimbusFlow API Authentication

This is fictional test documentation for the prodRAG demo.

## Authentication format

NimbusFlow API requests use an API key in the HTTP `Authorization` header with the `Bearer`
scheme. Keys created for production start with `nf_live_`; test keys start with `nf_test_`.
Example values in documentation are placeholders and must never be used as credentials.

An HTTP `401 Unauthorized` response usually means the key is missing, revoked, copied with
extra whitespace, or created for a different NimbusFlow environment. An HTTP `403 Forbidden`
response means the key is valid but lacks permission for the requested operation.

## Rotation

Workspace administrators rotate keys under **Settings > Developers > API keys**. Create the
replacement, update the application, verify a test request, and then revoke the old key. For a
scheduled rotation, both keys can remain active for up to 15 minutes.

## Secret handling

Never paste an API key, access token, client secret, password, private key, or signed session
token into a support ticket. If a secret is exposed, revoke it immediately and create a new one.
Support must route a ticket containing a secret to the secure human-support channel. Logs shared
with support should show only the first four and final four characters of a key.
