---
id: forum-429-workaround
title: Community: Working around 429 rate limit errors
source: forum
---
Posted by scriptkid_88. My nightly sync keeps hitting E101 rate limit errors on the Pro plan. Workarounds that helped: batch item updates using the bulk endpoint which counts once per hundred items, cache read heavy calls locally for sixty seconds, and spread jobs across the minute with random jitter instead of starting all at the top of the minute. Reply from ops_marta: also check whether a forgotten test script shares the same workspace, because limits are per workspace not per key. A support engineer added that temporary increases are possible for migrations. Marked as solved with the batching approach reducing calls by ninety percent.
