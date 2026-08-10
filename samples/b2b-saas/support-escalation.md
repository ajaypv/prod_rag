# NimbusFlow Support Escalation and Data Handling

This is fictional test documentation for the prodRAG demo.

## Automatic-answer policy

The assistant may answer a ticket when retrieved documentation supports the response and every
factual statement cites a source. High- and medium-confidence answers can be sent automatically
in this demo. Low-confidence tickets require human review and must not receive a guessed answer.

The confidence label describes retrieval evidence, not the probability that every sentence is
correct. Support owners must validate thresholds against labeled customer questions before using
automatic replies in production.

## Sensitive data

Send a ticket to human review when it contains an API key, access token, client secret, password,
private key, payment-card number, or government identifier. The assistant should identify only
the data type. It must not repeat, store in logs, embed, rerank, or send the sensitive value to a
chat model.

Ask the customer to revoke exposed credentials and resubmit the question with redacted values.
Payment and identity data must use the approved secure support channel.

## Business escalation rules

Route refund requests, duplicate charges, fraud concerns, and billing disputes over USD 500 to
Billing Operations. Route permanent API-limit increases, limits above 600 requests per minute,
and contract-specific capacity questions to Capacity Engineering. Route repeated Salesforce or
webhook failures that meet their runbook thresholds to Integration Engineering.

## Unsupported questions

If the documents do not cover the question, state that evidence is insufficient and request
human review. Do not use general model knowledge to fill a documentation gap.
