# Environment Variables

As we're following the 12 factors, everything can be configured using
environment variables.

## Environment variables

-   Required basic values &mdash; Those things cannot be invented nor have
    decent default value. You need to specify them.
    -   `DATABASE_URL` &mdash; The URL to the database (must be a PostgreSQL DB)
    -   `ENVIRONMENT` &mdash; Name of the environment (current branch name,
        develop, etc)
    -   `SECRET_KEY` &mdash; Django's secret key value
-   Cache/Queue
    -   `REDIS_URL` &mdash; Base URL of the Redis. It will be used by several
        services (cache, queue, etc), each with a different (auto-generated)
        prefix.
-   Helper features
    -   `DEBUG` (YAML) &mdash; Enables debug mode
    -   `POOL_DB_CONNECTIONS` (YAML) &mdash; Enable this in production to enable
        DB connection pooling
    -   `SENTRY_DSN` &mdash; Set here the Sentry DSN to enable reporting
        exceptions to Sentry
    -   `TIME_ZONE` &mdash; Default time zone to be used by Django
-   External communications
    -   `ENABLE_EMAILS` (YAML) &mdash; Without this enabled, emails will not be
        sent but rather printed to the console

## Preset implementation

Here's the documentation from the preset code to understand how those are used:

```{eval-rst}
.. autoclass:: model_w.preset.django.ModelWDjango
   :members:

   .. automethod:: __init__
```
