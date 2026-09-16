# Gaia Assignment: Durable Refund Support Agent

This project implements a durable orchestration layer for a customer-support refund workflow.
The agent retrieves case information, evaluates refund eligibility, pauses for human approval,
issues a refund, waits for provider confirmation, and notifies the customer.

The first implementation is intentionally small and uses mocked tools so the reliability behavior
can be tested without external services.

## Documentation

- [Workflow specification](docs/workflow-spec.md)
- [Initial acceptance scenario](docs/scenarios.md)
- [Run and step state model](docs/state-model.md)
- [Architecture and design decisions](docs/architecture.md)

Implementation and run instructions will be added next.
