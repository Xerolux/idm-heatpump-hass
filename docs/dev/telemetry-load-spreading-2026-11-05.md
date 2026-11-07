# Fleet load spreading — private build 0.26.0-b7

## Expected load and limits

Five hundred daily reports average one upload every 172.8 seconds. The important
risk is synchronized activation/recovery, not that steady average. Firmware adds
roughly four requests per consenting installation per day. No adoption count is
interpreted as consent; both opt-ins remain off by default and independent.

The backend already bounds concurrency to twelve request threads and two archive
uploads. The live nginx request zone was verified to use the client IP, not a
global fleet key. It retains the existing per-IP rate limits. Capacity inspection
showed approximately 548 GiB disk free and 8,462 MiB memory available at the time
of deployment; this is a snapshot, not an ongoing capacity guarantee.

## Client behavior

First telemetry slots are randomly 24–48 hours after consent. Later attempts are
24–25 hours apart, including failed attempts. The exact next slot is written
before network I/O and survives reloads. Existing stores migrate once to a random
slot without losing counters or the frozen outbox. Overdue reconnects are delayed
randomly by up to one hour. No immediate retry or bulk backlog replay occurs.
The one-minute local due check does not itself contact any server; actual execution
may follow the scheduled instant at the next tick or later if HA is busy.

Firmware queries wait randomly up to 30 minutes after setup, then use six hours
plus up to 30 minutes of jitter. Their sensor initially reports a scheduled state
and next-check attribute. Requests remain bounded by timeout and consent withdrawal.
No firmware identity, operating counters or persistent query queue was introduced.

## Server index and retention

The private firmware index decrypts only newly appended reports and answers
subsequent queries from controller/model/version aggregates. It caches no myIDM
IDs or operating counters. A lock serializes index updates across request threads.
A heap removes expired observations on reads and hourly cleanup, including idle
indexes. Verified erasure invalidates the index immediately. Reused SQLite rowids
are detected and safely rebuild the index.

The report cap is 250,000, enough for 500 daily reports over a leap-year-length
retention window (183,000) with headroom. The existing twelve-calendar-month expiry
and 8 KiB report bound remain unchanged. At the cap, the payload bound is about
2 GB before encryption/database/index overhead. Disk monitoring remains necessary.

## Verification

Local scheduling tests simulate 500 simultaneous opt-ins, 500 overdue reconnects
and 500 firmware startups without network traffic. They check distribution,
persisted slots, consent gates and absence of startup/retry bursts. The backend
suite sends 500 concurrent local catalog queries over 500 synthetic reports:
existing reports are decrypted once in total, and one new report adds exactly
one decode. Erasure, expiry, idle cleanup and rowid reuse are covered.

All load tests use local temporary stores and mocks, never 500 real requests to
the production service. Deployment verification uses a small synthetic ingest,
deduplication, firmware and verified-erasure cycle; synthetic rows are removed.
Real HA installation preserves entry options, connection settings and aggregates,
without forcing a daily upload or sending plant-control commands. There is no
public release, tag or git push.
