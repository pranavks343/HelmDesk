---
id: forum-backup-bucket
title: Community: Backup fails with E115 on custom bucket
source: forum
---
Posted by infra_ivan. Our backups started failing with E115 after we rotated our storage credentials. The cause was that the bucket policy no longer allowed the Nimbus service account to write objects. Adding the s3 PutObject permission back for the Nimbus principal fixed it, and the next scheduled backup succeeded. Reply from cloud_lena: also verify the bucket is in a region reachable by Nimbus and that server side encryption settings match. If you still see failures, run a manual backup and read the error details in the backup log. Solved.
