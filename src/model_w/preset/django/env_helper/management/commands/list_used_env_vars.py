import json
from argparse import ArgumentParser
from enum import Enum
from typing import Optional

from django.conf import settings
from django.core.management import BaseCommand
from django.utils.translation import gettext as _
from rich.console import Console
from rich.table import Table


class Format(Enum):
    """
    The possible output formats
    """

    table = "table"
    json = "json"


def yes_no(x, warn: Optional[bool] = None):
    """
    Displays either "yes" or "no" given the truth-ish-ness of the input
    variable. You can specify if you want a warning for a given value, which
    allows to make either yes or no to stand out in the table.

    Parameters
    ----------
    x
        Value to test
    warn
        Value for which to display a warning
    """

    if x:
        val = _("Yes")
    else:
        val = _("No")

    if warn == bool(x):
        return f"[bold magenta]{val}"
    else:
        return val


class Command(BaseCommand):
    """
    Utility command to list all environment variables that were used during
    configuration.
    """

    def add_arguments(self, parser: ArgumentParser):
        """
        We'll allow the user to select an output format
        """

        parser.add_argument(
            "-f",
            "--output-format",
            type=Format,
            help=_("Output format. Choices: table or json. Default to table."),
            default=Format.table,
        )

    def handle(self, output_format: Format, *args, **options):
        """
        Uses the env manager in order to know which environment variables have
        been used to configure this Django.
        """

        out = None
        table = None

        match output_format:
            case Format.table:
                table = Table(
                    title=_("Used env vars"),
                    title_style="bold cyan",
                    title_justify="left",
                )

                table.add_column("Name", style="cyan")
                table.add_column("Is Required?")
                table.add_column("Is YAML?")
            case Format.json:
                out = []

        for name, info in sorted(settings.USED_ENV_VARS.items()):
            match output_format:
                case Format.table:
                    table.add_row(
                        name,
                        yes_no(info["is_required"], True),
                        yes_no(info["is_yaml"], True),
                    )
                case Format.json:
                    out.append(
                        dict(
                            name=name,
                            is_required=info["is_required"],
                            is_yaml=info["is_yaml"],
                        )
                    )

        match output_format:
            case Format.table:
                console = Console()
                console.print(table)
            case Format.json:
                print(json.dumps(out, indent=4))
