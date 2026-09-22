---
id: changelog-outage-postmortem
title: Post-mortem: API Outage on 14 August
source: changelog
---
On 14 August between 09:12 and 10:47 UTC the Nimbus API returned elevated errors, including E105 timeouts and E101 false rate limit responses, for workspaces in the EU region. Incident INC-204. Root cause: a misconfigured connection pool limit deployed with a routine release exhausted database connections under peak load. Impact: about twelve percent of requests failed during the window. Resolution: the release was rolled back at 10:31 UTC and capacity fully recovered by 10:47. Follow up actions include load testing connection limits before deploys, adding alerts on pool saturation and issuing service credits to affected Enterprise customers. Customers who were charged for the affected day on monthly plans may request a refund.
