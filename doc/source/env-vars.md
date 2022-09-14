# Environment Variables

As we're following the 12 factors, everything can be configured using
environment variables.

## Environment variables

-   Required basic values &mdash; Those things cannot be invented nor have
    decent default value. You need to specify them.
    -   `DATABASE_URL` &mdash; The URL to the database (must be a PostgreSQL DB)
    -   `ENVIRONMENT` &mdash; Name of the environment (current branch name,
        develop, etc). That's only required in production, if the current user
        seems to have a home in `/home` we'll invent an environment name based
        on the user name and the DB name.
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
-   External communications &mdash; See below

## External communications

The preset comes with Wailer and thus the ability to send emails or SMS.

Both systems work with the same idea:

-   Can be entirely configured with environment variables
-   Supports different backends
-   Safe by default: print to console unless asked otherwise and pure in-memory
    implementation during unit testing, so that communications don't leave the
    developer's machine

### Email

The emails can be configured with the `EMAIL_MODE` environment variables, that
has 3 possible values, with associated environment variables:

-   `console` &mdash; Default print-to-console backend
-   `mailjet` &mdash; Using Mailjet to send emails
    -   `MAILJET_API_KEY_PUBLIC` &mdash; Public API key
    -   `MAILJET_API_KEY_PRIVATE` &mdash; Private API key
-   `mandrill` &mdash; Using Mandrill to send emails
    -   `MANDRILL_API_KEY` &mdash; Mandrill's API key

### SMS

It's the same concept, driven by `SMS_MODE`:

-   `console` &mdash; Default print-to-console backend
-   `mailjet` &mdash; Using Mailjet to send SMSes
    -   `MAILJET_API_TOKEN` &mdash; API token for SMS sending

## Preset implementation

Here's the documentation from the preset code to understand how those are used:

```{eval-rst}
.. autoclass:: model_w.preset.django.ModelWDjango
   :members:

   .. automethod:: __init__
```
