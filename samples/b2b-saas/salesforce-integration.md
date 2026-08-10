# NimbusFlow Salesforce Integration

This is fictional test documentation for the prodRAG demo.

## Connection requirements

The NimbusFlow Salesforce integration uses OAuth 2.0. The connecting Salesforce user must have
API Enabled permission and read/write access to every synchronized object and field. NimbusFlow
does not store the user's Salesforce password.

## Reconnect after authorization failure

An `invalid_grant` error means the Salesforce refresh token is invalid or revoked. A NimbusFlow
workspace administrator should open **Settings > Integrations > Salesforce**, select
**Reconnect**, sign in to Salesforce, and approve access again. Reconnecting does not delete the
existing field mapping.

An `INSUFFICIENT_ACCESS` error means OAuth succeeded but the Salesforce user cannot access an
object, record, or field. Update the Salesforce permission set before retrying the sync.

## Sync behavior

NimbusFlow polls Salesforce every 15 minutes and sends local changes within two minutes. A full
resync can take up to six hours. Do not start multiple full resyncs for the same workspace.

Support can troubleshoot permission and mapping errors with the workspace ID, Salesforce object
name, sync job ID, and UTC timestamp. Escalate to Integration Engineering when five consecutive
syncs fail after reconnection, when mappings disappear, or when the failure affects more than
10,000 records.
