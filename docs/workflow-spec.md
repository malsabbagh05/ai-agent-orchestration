# Refund Support Agent Workflow Specification

## Purpose

The agent processes one customer refund request through a durable, multi-step workflow. It
retrieves the relevant information, evaluates the refund policy, obtains human approval,
issues the refund, waits for payment-provider confirmation, and notifies the customer.

The workflow must preserve enough state to pause, resume after an application restart, retry
transient failures, and prevent duplicate side effects.

## Scope and policy

A request is eligible when:

- The order is no more than 30 days old.
- The order has not already been refunded.
- The order exists and belongs to the requesting customer.

Additional rules:

- Every eligible refund requires human approval.
- An eligible request receives a full refund.
- The customer is notified only after the payment provider confirms the refund.
- Ineligible requests do not require human approval.
- Refund and notification actions must be idempotent.

Partial refunds, exchanges, multiple orders, real payment integrations, real customer
communication services, authentication, and multiple agents are outside the first slice.

## Actors and boundaries

- **Support caller:** submits a refund request and inspects the run.
- **Orchestrator:** owns run progression, checkpoints, pauses, retries, and cancellation.
- **Refund agent:** evaluates the request and recommends an outcome. It may be mocked; it
  does not own durable state or bypass approval.
- **Human approver:** approves or rejects an eligible refund.
- **Payment provider:** emits a simulated refund-confirmation event.
- **Tools:** retrieve support, order, and refund data, issue a refund, and send a notification.
- **Persistent store:** saves run state, step state, results, pause information, and trace data.

## Workflow steps

1. **Collect case context**
   - Retrieve the support request, order, and refund history.

2. **Assess eligibility**
   - Evaluate the policy and record the recommendation and reason.

3. **Approve and issue refund**
   - Pause for human approval.
   - If approved, issue the refund exactly once.

4. **Await provider confirmation**
   - Pause until a simulated provider-confirmation event is received.

5. **Notify customer**
   - Send the final refund outcome to the customer.

## Tool interfaces

The first implementation may use mocked tools:

- `get_support_request`
- `get_order`
- `get_refund_history`
- `issue_refund`
- `send_customer_notification`

The first three are read tools. The last two are side-effecting tools.

## Run and step states

A run can be:

- `pending`: created but not started.
- `running`: actively executing a step.
- `paused`: waiting for approval or an external event.
- `completed`: finished, including an ineligible or rejected business outcome.
- `failed`: stopped because of a non-retryable error or exhausted retries.
- `cancelled`: deliberately stopped before completion.

A step can be:

- `pending`
- `running`
- `paused`
- `completed`
- `failed`
- `skipped`
- `cancelled`

## Pause and checkpoint rules

- The approval pause occurs before the refund tool is called.
- After an approved refund succeeds, the refund result is persisted before waiting for the
  provider event.
- The provider-confirmation pause stores its reason and the information needed to resume.
- A completed step is never re-executed when a run is resumed.
- Run and step state are persisted after each meaningful transition.

## Idempotency rules

Side-effecting actions use stable keys derived from the refund request:

```text
refund:<request_id>
notification:<request_id>
```

Retries and duplicate resume requests must reuse the same key. Before performing a side effect,
the orchestrator checks whether the step already has a recorded successful result or whether the
tool has already accepted the key.

## Trace requirements

Each step execution records:

- Run ID
- Step name
- Step status
- Start and completion timestamps
- Tool invoked, if any
- Retry attempt and retry limit
- Pause reason, if any
- Approval decision, if any
- Error information, without secrets
