---
id: webhooks
title: Webhooks Guide
source: docs
---
Webhooks let Nimbus notify your systems when events happen, such as project creation, backup completion or invoice payment. Create a webhook under Settings, Integrations, Webhooks by entering an HTTPS endpoint and choosing events. Each delivery is signed with an HMAC SHA-256 signature in the X-Nimbus-Signature header; verify it using your signing secret before trusting the payload. Your endpoint must respond with a 2xx status within ten seconds. Failed deliveries are retried up to eight times over twenty four hours with exponential backoff. After repeated failures the webhook is disabled and you see error E118 in the dashboard. Events may arrive out of order, so use the created timestamp and the event id for deduplication. Webhook deliveries do not count against API rate limits.
