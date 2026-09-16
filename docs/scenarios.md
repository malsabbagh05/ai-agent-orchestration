# Refund Support Agent Scenarios

## Scenario 1: Eligible request is approved and completed

**Given**

- Refund request `REQ-1001` belongs to customer `CUST-1001`.
- Order `ORD-1001` exists and was placed 10 days ago.
- The order amount is 100.00 USD.
- The order has not been refunded.
- The payment provider will eventually confirm the refund.

**When**

1. A new agent run is started for `REQ-1001`.
2. The agent retrieves the support request, order, and refund history.
3. The agent evaluates the request as eligible.
4. The run pauses for human approval.
5. The approval is accepted.
6. The agent issues the full refund.
7. The run pauses while waiting for provider confirmation.
8. The application process stops and starts again.
9. The same run is loaded and resumed with the provider confirmation event.
10. The agent sends a refund confirmation to the customer.

**Then**

- The run ends in `completed` with business outcome `refunded`.
- Steps 1 and 2 are completed before the approval pause.
- Step 3 records the approval and performs the refund after approval.
- The refund action is performed exactly once.
- The notification action is performed exactly once.
- The run resumes from the provider-confirmation checkpoint after restart.
- Previously completed steps are not executed again.
- The trace records the approval pause and provider-confirmation pause.
- The trace records the refund and notification tool calls, timestamps, and outcomes.

## Scenario 2: Ineligible request is completed without a refund

**Given**

- The order is older than the 30-day policy window, belongs to another customer, or already has a
  refund.

**When**

1. A run is started and the case context is collected.
2. Eligibility is assessed.

**Then**

- The run ends in `completed` with business outcome `ineligible`.
- The approval, refund, provider, and notification steps are skipped.
- No side-effecting tool is called.

## Scenario 3: Human approval is rejected

**Given**

- The request is eligible and the run is paused for approval.

**When**

1. The approver rejects the request.

**Then**

- The run ends in `completed` with business outcome `rejected`.
- The refund is never issued and later steps are skipped.
- Repeating the same rejection is safe; a conflicting decision is rejected.

## Scenario 4: Restart while waiting for the provider

**Given**

- The request was approved and the refund provider accepted the refund submission.

**When**

1. The application process stops while the run is paused for `refund.confirmed`.
2. A new process opens the same SQLite database.
3. The run is resumed with `refund.confirmed`.

**Then**

- The completed refund step is loaded from SQLite and is not executed again.
- The notification is sent once and the run completes as `refunded`.

## Scenario 5: Temporary and permanent tool failures

**Given**

- A read or action tool reports either a temporary timeout or a permanent error.

**When**

1. The runner invokes the tool.

**Then**

- Temporary failures are retried with a bounded exponential delay and every attempt appears in the
  trace.
- A permanent failure, or exhausted retries, marks the step and run as `failed` with an error type
  and message.

## Scenario 6: Cancellation and execution bounds

**Given**

- A run is pending, running, or paused.

**When**

1. A caller cancels the run, or a configured step/tool-call limit is reached.

**Then**

- Cancellation marks the run and every unfinished step as `cancelled`; no later side effect runs.
- A limit breach marks the run as `failed` and records the bound violation in the trace.
