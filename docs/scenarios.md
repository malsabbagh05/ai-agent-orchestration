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
