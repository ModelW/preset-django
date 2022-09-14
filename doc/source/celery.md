# Celery

This preset handles Celery and will enable by default if it is installed.

## Installing

The simplest way to get Celery installed is to add the `celery` extra dependency
when installing `modelw-preset-django`.

With pip this means:

```
pip install modelw-preset-django[celery]
```

In a Poetry `pyproject.toml`:

```toml
[tool.poetry]
# blah blah

[tool.poetry.dependencies]
# blah blah
modelw-preset-django = { version = "~2022.10", extras = ["celery"] }

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"
```

## Usage in settings

By default, if the Celery packages are installed then the configuration will
automatically be activated. However,
the{py:class}`~.model_w.preset.django.ModelWDjango` preset has a `enable_celery`
setting that you can change as well.

```python
from model_w.env_manager import EnvManager
from model_w.preset.django import ModelWDjango

# You can force Celery activation like this, but it's really not mandatory
with EnvManager(ModelWDjango(enable_celery=True)) as env:
    pass
```

## Default settings

While of course you can override any setting you'd like, by default we'll set
this:

-   `CELERY_RESULT_BACKEND` will be `django-db` (you can see it in the Django
    Admin)
-   `CELERY_CACHE_BACKEND` will be `django-cache` (which is Redis)
-   `CELERY_BROKER_URL` will be the Redis instance from the `REDIS_URL`
    environment variable (that is also used by the cache)
-   `CELERY_BEAT_SCHEDULER` is the simplest one, `celery.beat.Scheduler` because
    why deal with persistence when you usually don't need it? You can simply
    define beat tasks using the `CELERY_BEAT_SCHEDULE` setting. If you need a
    more complex scheduler, up to you to put what you want.

If you don't change the `CELERY_BROKER_URL` and keep it to the default value of
using Redis, then all the keys will be auto-prefixed in order to avoid collision
with other services like the cache that use the same Redis instance. This is
done by forcing the `global_keyprefix` setting into
`CELERY_BROKER_TRANSPORT_OPTIONS`.

On the other hand if you changed this value you're on your own.

### Other settings

I've lied. More settings are set. It's more minor details, let's explain them
here:

-   `CELERY_TIMEZONE` takes the same value as the Django time zone (to be
    consistent)
-   `CELERY_TASK_TRACK_STARTED` we track when tasks start as well as when they
    finish, in order to be more precise in the reporting. If/when that's causing
    performance issues, that's when you start wondering if it's a good idea or
    if the results backend is the right one
-   `CELERY_TASK_TIME_LIMIT` all men must die and that's the same for Celery
    tasks. It happens that tasks get stalled because of stupid IO timeouts not
    happening (looking at you requests) or literally anything else from dumb
    code to cosmic rays. We postulate that this won't happen _often_ but that it
    _will_ happen. We give tasks 1h (or whichever you set at init of the preset)
    to all tasks to finish, otherwise they will be forcefully killed.
-   `CELERY_TASK_REMOTE_TRACEBACKS` this allows to get much more details about
    the stack trace from dead tasks. It requires an extra dependency (that we
    declared) but who cares.
-   `CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS` I'm not
    thinking too much about this one but the docs say that it will be enabled by
    default in next version so we're just getting future-proofed

## Further steps

Once Celery is installed into the settings, there remains more steps to follow
that the preset cannot make on its own.

### Creating the Celery "app"

Usually Django apps have a module that contains the `settings.py`, `wsgi.py` and
so forth. That's in this module that we need to change things a bit, as
explained in the official
[tutorial](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html).

First let's add `celery.py` file:

```python
import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proj.settings')

app = Celery('proj')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()
```

Of course there you need to change `proj.settings` by your default settings
module (in doubt, look into your `manage.py` and you will find a similar line
that you can just copy here). Also don't hesitate to name your project something
else than `proj`.

Then let's modify the module's `__init__.py` to include that app:

```python
from .celery import app as celery_app
```

### Creating tasks

Well this is not a Celery tutorial, so go read that instead.

### Starting Celery

With the way we've configured it here, the commands to start Celery would be:

For **development** only:

```bash
# Worker and beat together
python -m celery -A demo_django.celery:app worker -B
```

Then in **production**, run those two in parallel:

```bash
# Starting the worker
python -m celery -A demo_django.celery:app worker

# Starting the beat
python -m celery -A demo_django.celery:app beat
```
