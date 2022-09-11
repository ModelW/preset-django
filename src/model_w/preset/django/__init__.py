import logging
from functools import cache
from pathlib import Path
from typing import Optional, Union

import coloredlogs
import sentry_sdk
from dj_database_url import parse as db_config
from django.core.exceptions import ImproperlyConfigured
from model_w.env_manager import AutoPreset, EnvManager
from model_w.env_manager._dotenv import find_dotenv  # noqa
from sentry_sdk.integrations.django import DjangoIntegration


class ModelWDjango(AutoPreset):
    """
    ModelW preset for Django running on PaaS platforms like DigitalOcean. Feel
    free to override any method if it doesn't suit your needs. All values that
    are set in :code:`pre_` methods can easily be overridden by just setting it
    from inside the settings.py.
    """

    def __init__(
        self,
        *,
        sentry_sample_rate: float = 1.0,
        base_dir: Optional[Union[str, Path]] = None,
        enable_postgis: bool = False,
        default_time_zone: str = "Europe/Madrid",
        url_prefix: str = "/back",
        conn_max_age_when_pooled: Union[int, float] = 60,
        enable_cache: bool = True,
    ):
        """
        You can set here different adjustments within the supported options

        Parameters
        ----------
        sentry_sample_rate
            Trace rate for Sentry performance tracing. Defaults to 1 for new
            projects but at scale you must reduce this value.
        base_dir
            Base dir of the Django project. In most setups that exist, this is
            the directory that contains the manage.py file. If this parameter
            is missing, that's how we'll determine the base directory, based
            on the location of manage.py.
        enable_postgis
            If your project does some geographical stuff, you need to enable
            PostGIS using this flag.
        default_time_zone
            The time zone to set by default in Django. Not very neutral default
            value for sure but we're a Madrid-based company so...
        url_prefix
            In PaaS platforms, it is convenient to have all the calls to the
            backend prefixed with a folder name. Here it's `/back` by default,
            meaning that you should configure your URLs to be `/back/admin`,
            `/back/api` and so forth. The usefulness of this value is for the
            settings like the static URL prefix.
        conn_max_age_when_pooled
            There is a POOL_DB_CONNECTIONS environment variable that enables
            connection pooling (by default connections will open/close at each
            request, which is slower but more cost-effective in some cases).
            This value indicates the conn_max_age (in seconds) when pooling is
            enabled.
        enable_cache
            Enables the cache engine (in Redis).
        """

        self.sentry_sample_rate = sentry_sample_rate
        self.base_dir: Path = self._guess_base_dir(base_dir)
        self.enable_postgis = enable_postgis
        self.default_time_zone = default_time_zone
        self.url_prefix = url_prefix.rstrip("/")
        self.conn_max_age_when_pooled = conn_max_age_when_pooled
        self.enable_cache = enable_cache

    def _guess_base_dir(self, base_dir: Optional[Union[str, Path]]) -> Path:
        """
        Guessing of the project's root directory based on where we can find a
        manage.py file up the stack trace. In most Django projects the
        manage.py file is indeed placed at the root. Even if not, that's
        generally a useful location.

        Parameters
        ----------
        base_dir
            Optional base directory. If set, it will be returned immediately.
            That's to be able to feed a "forced" base dir directly from above.
        """

        if base_dir is not None:
            return Path(base_dir)

        if manage := find_dotenv("manage.py"):
            return manage

        raise ImproperlyConfigured(
            "Cannot find BASE_DIR of project. Do you have a manage.py?"
        )

    def _redis_prefix(self, env: EnvManager, redis_use: str):
        """
        Computes a Redis prefix to be used in front of keys for some service
        (for example the cache or the Celery queue).

        Parameters
        ----------
        env
            Env manager
        redis_use
            What you're using this prefix for? "cache", "queue", etc.
        """

        return f"{self._environment(env)}:{redis_use}:"

    @cache
    def _redis_url(self, env: EnvManager):
        """
        Retrieves once the URL from environment variables so that the rest of
        the code can use it.
        """

        return env.get("REDIS_URL", "redis://localhost")

    @cache
    def _debug(self, env: EnvManager):
        """
        Retrieves once the debug mode from environment variables so that the
        rest of the code can use it.
        """

        return env.get("DEBUG", False, is_yaml=True)

    @cache
    def _environment(self, env: EnvManager):
        """
        Determines which is the environment, which is a mandatory environment
        variable. It can be "develop_remy" for a developer's environment,
        "production" for prod, "feature_42" for a feature branch, etc.
        """

        return env.get("ENVIRONMENT", build_default="_build")

    def pre_base_dir(self):
        """
        Saving the base dir into settings
        """

        yield "BASE_DIR", self.base_dir

    def pre_sentry(self, env: EnvManager):
        """
        Configures Sentry if the DSN is found
        """

        if env.get("SENTRY_DSN", None):
            sentry_sdk.init(
                integrations=[DjangoIntegration()],
                send_default_pii=True,
                traces_sample_rate=self.sentry_sample_rate,
                environment=self._environment(env),
            )

        return []

    def pre_basic_stuff(self, env: EnvManager):
        """
        A bunch of quite basic things that are common to all projects
        """

        yield "SECRET_KEY", env.get("SECRET_KEY", build_default="xxx")
        yield "DEBUG", self._debug(env)
        yield "ALLOWED_HOSTS", ["*"]
        yield "SECURE_PROXY_SSL_HEADER", ("HTTP_X_FORWARDED_PROTO", "https")
        yield "USE_X_FORWARDED_HOST", True
        yield "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField"
        yield "USED_ENV_VARS", env.read

    def pre_logging(self, env):
        """
        Configuring nice console logging, especially when in debug mode.
        We're setting exceptions for a lot of commonly used root modules that
        would otherwise spam the console.
        """

        coloredlogs.install(
            level=logging.DEBUG if self._debug(env) else logging.WARNING,
            fmt="%(asctime)s %(name)s[%(process)d] %(levelname)s %(message)s",
        )
        logging.getLogger("django.utils.autoreload").setLevel(logging.INFO)
        logging.getLogger("django.db.backends").setLevel(logging.INFO)
        logging.getLogger("django.template").setLevel(logging.INFO)
        logging.getLogger("django.request").setLevel(logging.INFO)
        logging.getLogger("asyncio").setLevel(logging.INFO)
        logging.getLogger("parso").setLevel(logging.INFO)
        logging.getLogger("s3transfer").setLevel(logging.INFO)
        logging.getLogger("botocore").setLevel(logging.INFO)
        logging.getLogger("boto3").setLevel(logging.INFO)
        logging.getLogger("PIL").setLevel(logging.INFO)
        logging.getLogger("boto3").setLevel(logging.WARNING)
        logging.getLogger("botocore").setLevel(logging.WARNING)

        yield "LOGGING_CONFIG", None

    def pre_database(self, env: EnvManager):
        """
        Database has to be PostgreSQL. We're using dj_database_url to parse the
        settings, but with a bunch of overridden things in the middle (like the
        connection pooling configuration or using the psqlextra backend).
        """

        pool = env.get("POOL_DB_CONNECTIONS", False, is_yaml=True)

        if url := env.get(
            "DATABASE_URL",
            build_default=f"{'postgis' if self.enable_postgis else 'postgresql'}://dum:dum@localhost/dummy",
        ):
            yield "DATABASES", {
                "default": db_config(
                    url=url,
                    conn_max_age=(self.conn_max_age_when_pooled if pool else 0),
                    engine="psqlextra.backend",
                )
            }

            if self.enable_postgis:
                yield "POSTGRES_EXTRA_DB_BACKEND_BASE", "django.contrib.gis.db.backends.postgis"

    def pre_password(self):
        """
        Our default password hasher is Argon2. It's much more secure than the
        rest for a much lower cost. The only reason why it's not the default
        in Django is that it requires an external dependency (but we don't mind
        depending on it so all is fine).
        """

        yield "PASSWORD_HASHERS", [
            "django.contrib.auth.hashers.Argon2PasswordHasher",
            "django.contrib.auth.hashers.PBKDF2PasswordHasher",
            "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
            "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
        ]

    def pre_languages(self, env: EnvManager):
        """
        Enabling localization features
        """

        yield "USE_I18N", True
        yield "USE_L10N", True
        yield "TIME_ZONE", env.get("TIME_ZONE", self.default_time_zone)

    def post_languages(self, context):
        """
        We're checking that some LANGUAGES are set and we can use the first
        language as default language for the app (this way you don't need to
        set LANGUAGES and LANGUAGE_CODE separately).
        """

        if not context.get("LANGUAGES"):
            raise ImproperlyConfigured("No languages found in LANGUAGES")

        yield "LANGUAGE_CODE", context["LANGUAGES"][0][0]

    def pre_static_files(self):
        """
        Configuring here static files. They'll be served by WhiteNoise (see
        below).
        """

        yield "STATICFILES_FINDERS", [
            "django.contrib.staticfiles.finders.FileSystemFinder",
            "django.contrib.staticfiles.finders.AppDirectoriesFinder",
        ]
        yield "STATICFILES_DIRS", []
        yield "STATIC_URL", f"{self.url_prefix}/static/"
        yield "STATIC_ROOT", self.base_dir / "static"

    def pre_middleware(self):
        """
        We're putting here the middlewares that come with a default Django
        project (as opposed to the default in Django which is just empty).
        Overall, good luck running your website without those.

        It is recommended that from your settings.py file you don't replace
        this list but rather you add your own middlewares to it by doing
        something like:

        >>> MIDDLEWARE = []
        >>> with EnvManager() as env:
        >>>     MIDDLEWARE.append("my.middleware.Class")

        Let's note in the example above the `MIDDLEWARE = []` line. It's just
        so that the IDE is not confused when EnvManager() sneakily adds
        MIDDLEWARE to local variables. It will still contain the values defined
        below, not an empty array.

        The reason to do like this is that if one day Django or Model W come
        with more interesting middlewares it'd be a shame to miss on them
        because you overrided the whole thing.
        """

        yield "MIDDLEWARE", [
            "django.middleware.security.SecurityMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
        ]

    def post_whitenoise(self, context):
        """
        We use WhiteNoise as static files storage engine and we make sure that
        it is present within middlewares.
        """

        yield "STATICFILES_STORAGE", "whitenoise.storage.CompressedManifestStaticFilesStorage"

        middleware = context.get("MIDDLEWARE")

        if (
            not middleware
            or middleware[0] != "django.middleware.security.SecurityMiddleware"
        ):
            raise ImproperlyConfigured("SecurityMiddleware is not the first middleware")

        if "whitenoise.middleware.WhiteNoiseMiddleware" not in middleware:
            middleware.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

        yield "MIDDLEWARE", middleware

    def pre_templates(self):
        """
        Basic template config from default Django settings
        """

        yield "TEMPLATES", [
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [],
                "APP_DIRS": True,
                "OPTIONS": {
                    "context_processors": [
                        "django.template.context_processors.debug",
                        "django.template.context_processors.request",
                        "django.contrib.auth.context_processors.auth",
                        "django.contrib.messages.context_processors.messages",
                    ]
                },
            }
        ]

    def pre_cache(self, env):
        """
        Let's configure the cache engine to use Redis
        """

        if self.enable_cache:
            yield "CACHES", {
                "default": {
                    "BACKEND": "django.core.cache.backends.redis.RedisCache",
                    "LOCATION": self._redis_url(env),
                    "KEY_PREFIX": self._redis_prefix(env, "cache"),
                }
            }

    def post_email(self, env: EnvManager):
        """
        Configuring emails sending. Unless an environment variable explicitly
        enables emails, they will be printed on the console for obvious safety
        reasons.
        """

        if not env.get("ENABLE_EMAILS", False, is_yaml=True):
            yield "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"

    def pre_drf(self):
        """
        Some basic DRF configuration, feel free to make it your own
        """

        yield "REST_FRAMEWORK", {
            "DEFAULT_AUTHENTICATION_CLASSES": (
                "rest_framework.authentication.SessionAuthentication",
            ),
            "DEFAULT_PERMISSION_CLASSES": (
                "rest_framework.permissions.IsAuthenticated",
            ),
            # 60 can be divided by 2, 3, 4 or 5 (and following multiples) which falls
            # nicely with most column layouts
            "PAGE_SIZE": 60,
        }

    def post_helper(self, context):
        """
        This preset comes with a Django app that brings a settings helper. It
        has no models on its own so it's really just the command. We
        discretely insert the app into the INSTALLED_APPS, shouldn't be too
        intrusive.
        """

        if not (installed := context["INSTALLED_APPS"]):
            raise ImproperlyConfigured("INSTALLED_APPS not found in configuration")

        if "model_w.preset.django.env_helper" not in installed:
            yield "INSTALLED_APPS", [*installed, "model_w.preset.django.env_helper"]
