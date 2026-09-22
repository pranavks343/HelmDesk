---
id: forum-webhook-signature
title: Community: Webhook signature verification fails
source: forum
---
Posted by hooks_hannah. Signature verification of Nimbus webhooks fails in my Node service. The fix was to compute the HMAC over the raw request body bytes, not over the parsed and re-serialised JSON, because whitespace changes alter the digest. Also compare digests with a constant time function. Reply from sec_omar: rotate the signing secret if you ever logged it. Another member noted that a proxy which decompresses or rewrites the body will break verification, so mount the raw body middleware before any JSON parser. Solved.
