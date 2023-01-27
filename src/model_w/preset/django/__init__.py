import logging
from functools import cache
from pathlib import Path
from typing import List, NamedTuple, Optional, Union

import coloredlogs
import sentry_sdk
from dj_database_url import parse as db_config
from django.core.exceptions import ImproperlyConfigured
from model_w.env_manager import AutoPreset, EnvManager, no_default
from model_w.env_manager._dotenv import find_dotenv  # noqa
from sentry_sdk.integrations.django import DjangoIntegration

__version__ = (
    __import__("pkg_resources").get_distribution("modelw-preset-django").version
)

__all__ = ["ModelWDjango"]


class InjectedInstall(NamedTuple):
    priority: int
    name: str


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
        enable_celery: Optional[bool] = None,
        celery_task_track_started: bool = True,
        celery_task_time_limit: float | int = 3600,
        enable_channels: Optional[bool] = None,
        enable_wagtail: Optional[bool] = None,
        enable_storages: Optional[bool] = None,
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
        enable_celery
            Enables a default configuration for Celery, that can then be
            overridden. By default it will enable itself if Celery can be
            imported. Celery will be installed if you install the celery
            extra dependency (pip install modelw-preset-django[celery]).
        celery_task_track_started
            Enable or not the tracking of tasks start
        celery_task_time_limit
            Maximum duration before a worker gets killed on a task (hard
            limit). Choose something wide but choose something. The default of
            1h seems reasonable. This avoids stalled processes (requests
            without timeout...) clogging the queue.
        enable_channels
            Enables Django Channels (which will configure it to use Redis). By
            default it will detect if channels is present and enable it
            automatically if so. You can just request the "channels" extra to
            this package.
        """

        self.sentry_sample_rate = sentry_sample_rate
        self.base_dir: Path = self._guess_base_dir(base_dir)
        self.enable_postgis = enable_postgis
        self.default_time_zone = default_time_zone
        self.url_prefix = url_prefix.rstrip("/")
        self.conn_max_age_when_pooled = conn_max_age_when_pooled
        self.enable_cache = enable_cache

        if enable_celery is None:
            try:
                import celery
                import django_celery_results
                import redis
            except ImportError:
                enable_celery = False
            else:
                enable_celery = True

        self.enable_celery: bool = enable_celery
        self.celery_task_track_started = celery_task_track_started
        self.celery_task_time_limit = celery_task_time_limit

        if enable_channels is None:
            try:
                import channels
                import daphne
                import redis
            except ImportError:
                enable_channels = False
            else:
                enable_channels = True

        self.enable_channels: bool = enable_channels
        self.injected_install: List[InjectedInstall] = []

        if enable_wagtail is None:
            try:
                import wagtail
            except ImportError:
                enable_wagtail = False
            else:
                enable_wagtail = True

        self.enable_wagtail = enable_wagtail

        if enable_storages is None:
            enable_storages = enable_wagtail

        self.enable_storages = enable_storages

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
            return manage.parent

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

        If we see that the user's home is in `/home` then we invent an
        environment name automatically based on the DB name. This kinds of
        ensure unicity in subsequent prefixes (for Redis) because if the DB
        name is unique locally then the prefix name shall be too.

        We don't do this in production because this should be a deliberate
        choice to name the environment and not just letting the default happen.
        """

        default = no_default

        if env.get("HOME", default="").startswith("/home/") and (
            user := env.get("USER", default="")
        ):
            db = dict(self.pre_database(env))

            if "DATABASES" in db and (
                db_name := db["DATABASES"]["default"]["NAME"]  # noqa
            ):
                default = f"{user}_{db_name}"

        return env.get("ENVIRONMENT", default=default, build_default="_build")

    def _install_app(self, context, app: str, priority: int = 100):
        """
        Utility to force an app into INSTALLED_APPS.

        Because order of appearance matters while execution of hooks is not
        guaranteed, we'll assign to each app a priority and we'll sort them
        out every time a new one shows up.

        Default priority is 100, including for apps that have been set from the
        config file.
        """

        present = set(x.name for x in self.injected_install)

        if app not in present:
            self.injected_install.append(InjectedInstall(priority, app))

        for other_app in context.get("INSTALLED_APPS", []):
            if other_app not in present:
                self.injected_install.append(InjectedInstall(100, other_app))

        yield "INSTALLED_APPS", [x.name for x in sorted(self.injected_install)]

    def pre_base_dir(self):
        """
        Saving the base dir into settings
        """

        yield "BASE_DIR", self.base_dir

    def pre_sentry(self, env: EnvManager):
        """
        Configures Sentry if the DSN is found
        """

        extra = []

        if self.enable_celery:
            from sentry_sdk.integrations.celery import CeleryIntegration

            extra.append(CeleryIntegration())

        if env.get("SENTRY_DSN", None):
            sentry_sdk.init(
                integrations=[DjangoIntegration(), *extra],
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
        logging.getLogger("django.utils.autoreload").setLevel(logging.WARNING)
        logging.getLogger("django.db.backends").setLevel(logging.INFO)
        logging.getLogger("django.template").setLevel(logging.INFO)
        logging.getLogger("django.request").setLevel(logging.ERROR)
        logging.getLogger("daphne.http_protocol").setLevel(logging.INFO)
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

        if not (langs := context.get("LANGUAGES")):
            raise ImproperlyConfigured("No languages found in LANGUAGES")

        yield "LANGUAGE_CODE", context["LANGUAGES"][0][0]

        if self.enable_wagtail and "WAGTAIL_CONTENT_LANGUAGES" not in context:
            yield "WAGTAIL_CONTENT_LANGUAGES", langs

        if self.enable_wagtail and "WAGTAILADMIN_PERMITTED_LANGUAGES" not in context:
            yield "WAGTAILADMIN_PERMITTED_LANGUAGES", langs

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

    def pre_wailer(self):
        """
        We're just defining those so that Wailer doesn't crash, however we'll
        let the user define their own emails/sms when then want.
        """

        yield "WAILER_EMAIL_TYPES", {}
        yield "WAILER_SMS_TYPES", {}

    def post_wailer(self, context):
        """
        Making sure that Wailer is installed in the apps
        """

        yield from self._install_app(context, "wailer", 80)

    def post_email(self, env: EnvManager):
        """
        Configuring emails sending. Unless an environment variable explicitly
        enables emails, they will be printed on the console for obvious safety
        reasons.
        """

        match env.get("EMAIL_MODE", default="console"):
            case "mailjet":
                yield "EMAIL_BACKEND", "wailer.backends.MailjetEmailBackend"
                yield "MAILJET_API_KEY_PUBLIC", env.get("MAILJET_API_KEY_PUBLIC")
                yield "MAILJET_API_KEY_PRIVATE", env.get("MAILJET_API_KEY_PRIVATE")
            case "mandrill":
                yield "EMAIL_BACKEND", "wailer.backends.MandrillEmailBackend"
                yield "MANDRILL_API_KEY", env.get("MANDRILL_API_KEY")
            case _:
                yield "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"

    def post_sms(self, env: EnvManager):
        """
        Configuring SMS sending. Unless an environment variable explicitly
        enables SMSes, they will be printed on the console for obvious safety
        reasons.
        """

        match env.get("SMS_MODE", default="console"):
            case "mailjet":
                yield "SMS_BACKEND", "wailer.backends.MailjetSmsBackend"
                yield "MAILJET_API_TOKEN", env.get("MAILJET_API_TOKEN")
            case _:
                yield "SMS_BACKEND", "sms.backends.console.SmsBackend"

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
            "DEFAULT_PAGINATION_CLASS": "model_w.preset.django.drf.LimitedPageNumberPagination",
            # 60 can be divided by 2, 3, 4 or 5 (and following multiples) which falls
            # nicely with most column layouts
            "PAGE_SIZE": 60,
        }

    def post_drf(self, context):
        """
        We're installing DRF
        """

        yield from self._install_app(context, "rest_framework", 80)
        yield from self._install_app(context, "rest_framework_gis", 80)

    def post_helper(self, context):
        """
        This preset comes with a Django app that brings a settings helper. It
        has no models on its own so it's really just the command. We
        discretely insert the app into the INSTALLED_APPS, shouldn't be too
        intrusive.
        """

        yield from self._install_app(context, "model_w.preset.django.env_helper", 90)

    def pre_celery(self, env: EnvManager):
        """
        When Celery is enabled, we inject some decent default using Redis as a
        broker and Django-backed backends.
        """

        if not self.enable_celery:
            return

        yield "CELERY_RESULT_BACKEND", "django-db"
        yield "CELERY_RESULT_EXTENDED", True
        yield "CELERY_BROKER_URL", self._redis_url(env)
        yield "CELERY_BEAT_SCHEDULER", "celery.beat.Scheduler"
        yield "CELERY_TIMEZONE", self.default_time_zone
        yield "CELERY_TASK_TRACK_STARTED", self.celery_task_track_started
        yield "CELERY_TASK_TIME_LIMIT", self.celery_task_time_limit
        yield "CELERY_TASK_REMOTE_TRACEBACKS", True
        yield "CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS", True

    def post_celery(self, env: EnvManager, context):
        """
        These settings are put in post because we want to give a chance to the
        user to override the broker URL. If they didn't do it, we proceed to
        hijacking the broker options to enforce a prefix in Redis keys.
        """

        if not self.enable_celery:
            return

        if context["CELERY_BROKER_URL"] != self._redis_url(env):
            return

        opts = context.get("CELERY_BROKER_TRANSPORT_OPTIONS", {})

        yield "CELERY_BROKER_TRANSPORT_OPTIONS", {
            **opts,
            "global_keyprefix": self._redis_prefix(env, "celery"),
        }

        yield from self._install_app(context, "django_celery_results", 80)

    def pre_channels(self, env: EnvManager):
        """
        If Channels is enabled we need to configure the broker to be Redis and
        to be prefixing properly its keys (otherwise we're at risk of conflict
        with the other parts of the app that also use Redis).
        """

        if not self.enable_channels:
            return

        yield "CHANNEL_LAYERS", {
            "default": {
                "BACKEND": "channels_redis.core.RedisChannelLayer",
                "CONFIG": {
                    "hosts": [self._redis_url(env)],
                    "prefix": self._redis_prefix(env, "channels"),
                },
            },
        }

    def post_channels(self, context):
        """
        Trying to be nice and adding channels to the installed apps.
        """

        if not self.enable_channels:
            return

        yield from self._install_app(context, "channels", 10)
        yield from self._install_app(context, "daphne", 10)

    def post_django_default(self, context):
        yield from self._install_app(context, "django.contrib.admin", 60)
        yield from self._install_app(context, "django.contrib.auth", 60)
        yield from self._install_app(context, "django.contrib.contenttypes", 60)
        yield from self._install_app(context, "django.contrib.messages", 60)
        yield from self._install_app(context, "django.contrib.sessions", 60)
        yield from self._install_app(context, "django.contrib.staticfiles", 60)

    def pre_storages(self, env):
        """
        If storages is enabled, we'll look to enable S3.

        There can be two modes to work with S3:

        - s3, when it's S3 storage on AWS cloud
        - do, when it's S3 storage on DigitalOcean

        Depending on this, different environment variables will be required.
        It will also detect if we're running from inside an AWS container or
        something of the sort in order to avoid manually setting the access key
        when Boto3 will determine it on its own.

        In do mode, the lib is configured to use the DigitalOcean endpoint
        instead of the default AWS one.
        """

        if not self.enable_storages:
            return

        yield "DEFAULT_FILE_STORAGE", "storages.backends.s3boto3.S3Boto3Storage"
        yield "AWS_S3_FILE_OVERWRITE", False

        is_aws = bool(env.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI", default=""))
        storage_mode = env.get("STORAGES_MODE", default="s3")

        if storage_mode == "do" or not is_aws:
            yield "AWS_ACCESS_KEY_ID", env.get("AWS_ACCESS_KEY_ID", build_default="xxx")
            yield "AWS_SECRET_ACCESS_KEY", env.get(
                "AWS_SECRET_ACCESS_KEY", build_default="xxx"
            )

        yield "AWS_STORAGE_BUCKET_NAME", env.get(
            "AWS_STORAGE_BUCKET_NAME", build_default="xxx"
        )

        if env.get("STORAGE_MAKE_FILES_PUBLIC", is_yaml=True, build_default=False):
            yield "AWS_S3_CUSTOM_DOMAIN", env.get("AWS_S3_CUSTOM_DOMAIN")
            yield "AWS_DEFAULT_ACL", "public-read"
            yield "AWS_S3_OBJECT_PARAMETERS", {
                "CacheControl": f"max-age={3600 * 24 * 365}",
            }

        if storage_mode == "do":
            do_region = env.get("DO_REGION", default="ams3")
            yield "AWS_S3_ENDPOINT_URL", f"https://{do_region}.digitaloceanspaces.com"

    def pre_wagtail(self):
        """
        Reasonable default settings for Wagtail
        """

        if not self.enable_wagtail:
            return

        yield "WAGTAIL_I18N_ENABLED", True
        yield "WAGTAIL_ALLOW_UNICODE_SLUGS", False
        yield "WAGTAIL_ENABLE_UPDATE_CHECK", False
        yield "TAGGIT_CASE_INSENSITIVE", True

    def post_wagtail(self, context):
        """
        Making sure Wagtail components and middlewares are loaded
        """

        if not self.enable_wagtail:
            return

        yield from self._install_app(context, "wagtail.contrib.forms", 70)
        yield from self._install_app(context, "wagtail.contrib.redirects", 70)
        yield from self._install_app(context, "wagtail.embeds", 71)
        yield from self._install_app(context, "wagtail.sites", 71)
        yield from self._install_app(context, "wagtail.users", 71)
        yield from self._install_app(context, "wagtail.snippets", 71)
        yield from self._install_app(context, "wagtail.documents", 71)
        yield from self._install_app(context, "wagtail.images", 71)
        yield from self._install_app(context, "wagtail.search", 71)
        yield from self._install_app(context, "wagtail.admin", 71)
        yield from self._install_app(context, "wagtail", 72)
        yield from self._install_app(context, "modelcluster", 73)
        yield from self._install_app(context, "taggit", 73)

        middleware = context.get("MIDDLEWARE")

        if "wagtail.contrib.redirects.middleware.RedirectMiddleware" not in middleware:
            middleware.append("wagtail.contrib.redirects.middleware.RedirectMiddleware")

        yield "MIDDLEWARE", middleware

    def pre_base_url(self, env):
        """
        Defining a BASE_URL and WAGTAIL_BASE_URL environment variable which is
        used both by Wagtail and by Wailer and potentially other systems in
        order to know which is the BASE_URL we should use for this website.
        It's helpful because things don't always come from an HTTP query (like
        crons) and thus you cannot always know the Host header.
        """

        base_url = env.get("BASE_URL", build_default="https://example.com")
        yield "BASE_URL", base_url

        if self.enable_wagtail:
            yield "WAGTAILADMIN_BASE_URL", base_url
