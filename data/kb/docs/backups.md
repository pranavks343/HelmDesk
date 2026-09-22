---
id: backups
title: Backups and Restore
source: docs
---
Nimbus creates automatic daily backups of every workspace at 02:00 UTC and keeps them for thirty days on Pro and ninety days on Enterprise. Free plans keep the last seven days. You can trigger a manual backup at any time from Settings, Data, Backups, and manual backups do not count against the daily schedule. To restore, choose a backup, click Restore and pick either in place or into a new workspace. Restoring in place replaces current data and cannot be undone, so we recommend restoring into a new workspace first to verify. Backups are encrypted with AES-256 and stored in a separate region. If a backup job fails with error E115, check that your custom storage bucket allows the Nimbus service account to write. Restore time depends on workspace size; typical workspaces under ten gigabytes restore in about fifteen minutes.
