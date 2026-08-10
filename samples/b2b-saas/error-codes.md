# NimbusFlow Support Error Code Runbook

This is fictional test documentation for the prodRAG demo.

## `BILLING_402_PAYMENT_REQUIRED`

The workspace has no successful payment after the three scheduled retries. Confirm that a
workspace owner updated the payment method. The next attempt begins within 30 minutes. Escalate
if the workspace remains read-only two hours after a successful payment.

## `API_429_RATE_LIMITED`

The workspace exceeded its rolling one-minute API allowance. Read the `Retry-After` header,
pause requests, and resume with exponential backoff and jitter. Creating another key does not
increase capacity.

## `AUTH_401_INVALID_KEY`

The API key is missing, revoked, malformed, or belongs to another environment. Check the header
scheme and remove accidental whitespace. Never collect the full key in a support ticket. Rotate
the key if exposure is suspected.

## `WEBHOOK_400_SIGNATURE_MISMATCH`

The receiver's HMAC-SHA256 digest differs from the request signature. Verify the current signing
secret, compute against the raw body, and check whether a proxy changed the payload. Share an
event ID rather than the signing secret.

## `INT_503_PROVIDER_UNAVAILABLE`

An external integration provider returned a temporary service failure. NimbusFlow retries for up
to 30 minutes. If failures continue beyond 30 minutes or affect more than one customer, route the
ticket to Integration Engineering and check the provider status page.
