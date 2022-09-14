# Channels

If you want to be doing WebSockets you're gonna need Django Channels. And while
there is not _much_ to configure (most of the work is just to code your
consumers and stuff), at least we'll take care of plugging Channels to the Redis
(that we're also using for Celery and the cache, what a busy lad).

## Installing

The simplest way to get Celery installed is to add the `channels` extra
dependency when installing `modelw-preset-django`.

With pip this means:

```
pip install modelw-preset-django[channels]
```

In a Poetry `pyproject.toml`:

```toml
[tool.poetry]
# blah blah

[tool.poetry.dependencies]
# blah blah
modelw-preset-django = { version = "~2022.10", extras = ["channels"] }

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"
```

## Default settings

Not much to be said that wasn't said yet. We're only setting `CHANNEL_LAYERS` to
use Redis. You can easily change options or add layers if you want:

```python
from model_w.env_manager import EnvManager
from model_w.preset.django import ModelWDjango

CHANNEL_LAYERS = {}

with EnvManager(ModelWDjango()) as env:
    # At this time, CHANNEL_LAYERS has been re-defined by the preset with the
    # default configuration, so you can just modify it

    CHANNEL_LAYERS['other_layer'] = {
        # whatever you want
    }
```
