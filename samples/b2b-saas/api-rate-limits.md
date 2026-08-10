# NimbusFlow API Rate Limits

This is fictional test documentation for the prodRAG demo.

## Default limits

API limits apply per workspace, not per API key. Starter workspaces allow 60 requests per
minute. Growth workspaces allow 300 requests per minute. Enterprise workspaces allow 1,200
requests per minute unless the order form states a different limit.

The service uses a rolling one-minute window. Short bursts are allowed only while capacity
remains in that window. Creating more API keys does not increase a workspace's limit.

## Rate-limit response

When the limit is reached, NimbusFlow returns HTTP `429 Too Many Requests` with these headers:

- `X-RateLimit-Limit`: the workspace limit for the current window
- `X-RateLimit-Remaining`: requests still available
- `X-RateLimit-Reset`: Unix time when capacity begins to recover
- `Retry-After`: minimum number of seconds before retrying

Clients should honor `Retry-After`, use exponential backoff with jitter, and cap retries at five
attempts. Retrying immediately can extend the failure and create duplicate work.

## Limit increases

Growth customers can request a temporary increase through support. Include the workspace ID,
expected requests per minute, burst duration, endpoint names, and business date. Human review is
required for all permanent increases and every request above 600 requests per minute. Enterprise
customers should follow the capacity process in their order form.
