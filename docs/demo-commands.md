# Demo Commands

Run these from the repository root. Copy the `run_id` printed by `start` and replace `<run_id>` in
the commands that follow.

```bash
rm -f data/runs.sqlite3 data/runs.sqlite3-wal data/runs.sqlite3-shm

python -m refund_agent start --request-id REQ-1001

python -m refund_agent inspect <run_id>

python -m refund_agent approve <run_id> --decision approve

python -m refund_agent inspect <run_id>

python -m refund_agent resume <run_id> --event refund.confirmed

python -m refund_agent inspect <run_id>

python -m refund_agent trace <run_id>
```
