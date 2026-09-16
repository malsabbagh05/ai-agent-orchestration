# Demo Transcript

The demo uses the default `data/runs.sqlite3` file. Remove an old demo database first if you want a
fresh run. The run identifier is printed by `start`; replace `<run_id>` below with that value.

```console
$ rm -f data/runs.sqlite3
$ python -m refund_agent start --request-id REQ-1001
{"run_id": "<run_id>"}

$ python -m refund_agent inspect <run_id>
{
  "run": {"run_id": "<run_id>", "status": "paused", "pause_reason": "approval", ...},
  "steps": [
    {"name": "collect_case_context", "status": "completed", ...},
    {"name": "assess_eligibility", "status": "completed", ...},
    {"name": "approve_and_issue_refund", "status": "paused", ...}
  ]
}

$ python -m refund_agent approve <run_id> --decision approve
{"business_outcome": null, "pause_reason": "provider_confirmation", "run_id": "<run_id>", "status": "paused"}

# The approve process has exited. A new CLI process now loads the checkpoint from SQLite.
$ python -m refund_agent resume <run_id> --event refund.confirmed
{"business_outcome": "refunded", "pause_reason": null, "run_id": "<run_id>", "status": "completed"}

$ python -m refund_agent inspect <run_id>
{
  "run": {"status": "completed", "business_outcome": "refunded", ...},
  "steps": [
    {"name": "await_provider_confirmation", "status": "completed", ...},
    {"name": "notify_customer", "status": "completed", ...}
  ]
}

$ python -m refund_agent trace <run_id>
[
  {"event": "step_paused", "pause_reason": "approval", ...},
  {"event": "tool_call_succeeded", "tool_name": "issue_refund", ...},
  {"event": "step_paused", "pause_reason": "provider_confirmation", ...},
  {"event": "tool_call_succeeded", "tool_name": "send_customer_notification", ...},
  {"event": "run_completed", ...}
]
```

The mock tools make the transcript deterministic. In a production integration, the same narrow
interfaces would call the support, payment, and messaging providers.
