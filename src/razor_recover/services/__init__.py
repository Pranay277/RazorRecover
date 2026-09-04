"""Read-only service layer for the merchant dashboard.

Houses the only place the dashboard endpoints talk to the database. Endpoints
stay thin (parse params, call a service, serialize). This service NEVER writes:
no retries, no executions, no state or policy changes, no attempt/decision/audit
creation. It only reads persisted rows.
"""
