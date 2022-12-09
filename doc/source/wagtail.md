# Wagtail

Wagtail is a powerful CMS based on Django. With great power comes great
dependencies, and Wagtail brings a lot of them. This preset handles most of
Wagtail-related problems with sane defaults, but don't hesitate to read the
documentation and adapt what you need.

## Installing

The simplest way to get Wagtail installed is to add the `wagtail` extra
dependency when installing `modelw-preset-django`.

With pip this means:

```
pip install modelw-preset-django[wagtail]
```

In a Poetry `pyproject.toml`:

```toml
[tool.poetry]
# blah blah

[tool.poetry.dependencies]
# blah blah
modelw-preset-django = { version = "~2022.10", extras = ["wagtail"] }

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"
```

## Usage in settings

By default, if the Wagtail packages are installed then the configuration will
automatically be activated. However, the
{py:class}`~.model_w.preset.django.ModelWDjango` preset has a `enable_wagtail`
setting that you can change as well.

```python
from model_w.env_manager import EnvManager
from model_w.preset.django import ModelWDjango

# You can force Wagtail activation like this, but it's really not mandatory
with EnvManager(ModelWDjango(enable_wagtail=True)) as env:
    pass
```

## Default settings

While of course you can override any setting you'd like, by default we'll set
this:

-   `WAGTAIL_CONTENT_LANGUAGES` copies `LANGUAGES` from Django
-   `WAGTAILADMIN_PERMITTED_LANGUAGES` copies `LANGUAGES` from Django
-   `WAGTAIL_I18N_ENABLED` will be enabled
-   `WAGTAIL_ALLOW_UNICODE_SLUGS` will be disabled
-   `WAGTAIL_ENABLE_UPDATE_CHECK` will be disabled (we don't want clients to see
    warnings about Wagtail updates)
-   `TAGGIT_CASE_INSENSITIVE` will be enabled (let's not have the same tag twice
    because of a case difference)
-   `WAGTAILADMIN_BASE_URL` will be set to `BASE_URL` from Django
-   All Wagtail-specific apps will be installed
-   The Wagtail redirect middleware will be installed

## Storage

Wagtail depends on a storage backend to be installed. By default it will
automatically activate the `django-storages` configuration. If not, parts of
Wagtail will fail.

See the [Storage](./storage.md) section for more information.

## More on Wagtail

It's recommended that you customize the `Image` and `Document` models in case
you need to modify them in the future. This is done by default in the
Model&nbsp;W project template but this is not a responsibility of this preset.
