# Installation

In order to install the Django Preset, you just need to add to your dependencies
the `modelw-preset-django` package. It contains in its dependencies precise
versions of the packages it configures your Django to use, including Django
itself (according to the Model W release versions).

Then you can use it in your `settings.py` file. Here is a minimalistic example:

```python
from model_w.env_manager import EnvManager
from model_w.preset.django import ModelWDjango

with EnvManager(ModelWDjango()) as env:
    INSTALLED_APPS = [
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
    ]

    ROOT_URLCONF = "demo_django.urls"

    WSGI_APPLICATION = "demo_django.wsgi.application"

    LANGUAGES = [
        ("en", "English"),
        ("fr", "French"),
    ]
```

Many values are set from the preset, based on the assumptions explained later
on.
