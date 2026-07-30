# Payment Service Timeout

## Symptoms

- Requests take longer than 30 seconds.

## Cause

- Database connection pool exhaustion.

## Resolution

- Restart database.
- Scale replicas.