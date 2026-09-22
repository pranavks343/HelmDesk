---
id: error-codes
title: Error Code Reference E101-E120
source: docs
---
This page lists the most common Nimbus error codes. E101 means the rate limit was exceeded; wait for Retry-After and slow down. E102 means the API key is invalid or revoked; create a new key under Settings, API. E105 means the request timed out upstream, usually during a regional incident; check the status page and retry. E110 means the SSO certificate has expired; upload fresh IdP metadata. E112 means the workspace storage quota is full; delete old backups or upgrade the plan. E115 means a backup job failed because the target bucket is unreachable; verify bucket permissions. E118 means a webhook endpoint returned repeated failures and was disabled; fix the endpoint and re-enable it. E120 means a payment method was declined during renewal and the workspace enters a seven day grace period. Always include the error code and request id when contacting support.
