"""
The ENVIRONMENT variable is mandatory, except on a developer's machine where
it gets invented from the user and the database name.

It used to be only invented when the user's home was in /home (Linux), so on
macOS and Windows a fresh project's settings failed to load. Django's
manage.py hides that error and carries on with its global defaults, which
showed up as "You must set settings.ALLOWED_HOSTS if DEBUG is False" even with
DEBUG=yes in the .env.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from model_w.env_manager import EnvManager

from model_w.preset.django import ModelWDjango

DATABASE_URL = "postgresql://user:password@localhost/proj_db"

#: Variables which the tests control, removed from the real environment
CONTROLLED = ["HOME", "USER", "USERNAME", "ENVIRONMENT", "DEBUG", "BUILD_MODE"]


@pytest.fixture
def environ(monkeypatch):
    """A clean environment, with only a database configured"""

    for name in CONTROLLED:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)

    return monkeypatch


def environment(tmp_path: Path) -> tuple[str, EnvManager]:
    """The environment name computed by the preset, and the env manager"""

    env = EnvManager(dotenv_path=False)
    value = ModelWDjango(base_dir=tmp_path)._environment(env)

    return value, env


@pytest.mark.parametrize(
    "variables",
    [
        pytest.param({"HOME": "/Users/dev", "USER": "dev"}, id="macos"),
        pytest.param({"USERNAME": "dev"}, id="windows"),
        pytest.param({"HOME": "/home/dev", "USER": "dev"}, id="linux"),
    ],
)
def test_invented_in_debug_on_every_os(environ, tmp_path, variables):
    environ.setenv("DEBUG", "yes")

    for name, value in variables.items():
        environ.setenv(name, value)

    value, env = environment(tmp_path)

    assert value == "dev_proj_db"
    assert not env.missing


def test_still_invented_from_a_linux_home(environ, tmp_path):
    """The historical behavior, even without DEBUG"""

    environ.setenv("HOME", "/home/dev")
    environ.setenv("USER", "dev")

    value, env = environment(tmp_path)

    assert value == "dev_proj_db"
    assert not env.missing


def test_mandatory_in_production(environ, tmp_path):
    environ.setenv("HOME", "/Users/dev")
    environ.setenv("USER", "dev")

    _, env = environment(tmp_path)

    assert "ENVIRONMENT" in env.missing


def test_explicit_value_wins(environ, tmp_path):
    environ.setenv("DEBUG", "yes")
    environ.setenv("USERNAME", "dev")
    environ.setenv("ENVIRONMENT", "staging")

    value, env = environment(tmp_path)

    assert value == "staging"
    assert not env.missing


SETTINGS = """
from model_w.env_manager import EnvManager
from model_w.preset.django import ModelWDjango

with EnvManager(ModelWDjango(base_dir={base_dir!r})) as env:
    LANGUAGES = [("en", "English")]
"""


@pytest.mark.parametrize(
    "variables",
    [
        pytest.param({"HOME": "/Users/dev", "USER": "dev"}, id="macos"),
        pytest.param({"USERNAME": "dev"}, id="windows"),
    ],
)
def test_fresh_project_settings_load(tmp_path, variables):
    """
    Like a freshly generated project: the .env only has DEBUG and the
    database, not ENVIRONMENT. Loading the settings must work and keep DEBUG.
    """

    (tmp_path / ".env").write_text(
        "DEBUG=yes\n"
        "SECRET_KEY=not-secret\n"
        "BASE_URL=http://localhost:3000\n"
        f"DATABASE_URL={DATABASE_URL}\n",
        encoding="utf-8",
    )
    (tmp_path / "settings.py").write_text(
        SETTINGS.format(base_dir=f"{tmp_path}"), encoding="utf-8"
    )

    env = {k: v for k, v in os.environ.items() if k not in CONTROLLED}
    env.update(variables)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import settings\n"
            "print(settings.DEBUG, settings.CACHES['default']['KEY_PREFIX'])",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["True", "dev_proj_db:cache:"]
