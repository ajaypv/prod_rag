# NimbusFlow Billing and Invoices

This is fictional test documentation for the prodRAG demo.

## Billing schedule

NimbusFlow bills subscriptions on the first day of each month at 00:00 UTC. The invoice
covers the upcoming monthly base subscription and the previous month's metered overages.
Annual subscriptions renew on the anniversary of the original purchase date.

Workspace owners can download invoices from **Settings > Billing > Invoices**. An invoice
normally appears within two hours of the billing run. If it is still missing after 24 hours,
support must escalate the ticket to the Billing Operations queue.

## Failed payments

NimbusFlow retries a failed card payment after 1 day, 3 days, and 7 days. The workspace stays
active during this seven-day grace period. If the third retry fails, the workspace becomes
read-only. Updating the card in **Settings > Billing > Payment method** starts a new payment
attempt within 30 minutes.

Support agents must not ask customers to paste a full card number, card security code, bank
account number, or password into a ticket. Route tickets containing payment credentials to the
secure human-support channel.

## Credits and refunds

Approved service credits appear on the next invoice. Refund requests are not approved
automatically. A Billing Operations agent must review duplicate charges, suspected fraud, and
refund requests over USD 500.

## Tax information

Customers can add a VAT or tax registration number under **Settings > Billing > Tax details**.
Tax changes apply to future invoices. NimbusFlow does not regenerate a finalized invoice solely
to add a missing tax number.
