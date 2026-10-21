# CommPal development guidance

- Use Python 3.14.7 and Django 6.0.
- Keep payments isolated in the `payments` app; future products should integrate through service/provider interfaces.
- Never handle or persist raw card numbers or CVC values. Use provider-hosted checkout.
- Preserve authentication, user ownership checks, idempotency, verified webhooks, and terminal payment states.
- Configure secrets and infrastructure using environment variables; never commit secrets.
- Run `python manage.py test` and `python manage.py check` after changes.
