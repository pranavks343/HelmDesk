---
id: api-rate-limits
title: API Rate Limits
source: docs
---
The Nimbus API limits requests per workspace using a rolling one minute window. Free plans may send 60 requests per minute, Pro plans 600 and Enterprise plans 6000. Every response includes the headers X-RateLimit-Limit, X-RateLimit-Remaining and X-RateLimit-Reset so clients can pace themselves. When you exceed the limit the API returns HTTP 429 with error code E101 and a Retry-After header in seconds. Clients should back off exponentially, starting at one second and doubling up to thirty seconds, with random jitter. Bulk endpoints count as one request per batch of one hundred items. Rate limits are shared by all API keys in a workspace, so a runaway script can starve your dashboard integrations. You can request a temporary limit increase from support for migrations, and Enterprise customers can purchase dedicated burst capacity. Webhooks are not counted against the limit.
