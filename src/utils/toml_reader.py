"""
This module provides the means to load settings from TOML configuration files.
"""

# Import from standard libraries
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Callable, Final

from tomllib import TOMLDecodeError, load

# Define types
type Primitive = bool | date | datetime | float | int | str | time
"""A type representing primitive data types in TOML."""
type AnyToml = Primitive | dict[str, AnyToml] | list[AnyToml]
"""A type representing all data types in TOML."""

# Define constants
DIR: Final[Path] = Path(__file__).parent
"""The path to this directory."""


# Define variables
TOMLDecodeError = TOMLDecodeError
"""An error raised if a document is not valid TOML."""


class Toml:
    """
    An abstract class for constructing TOML file parsers.
    """

    # Private attributes
    _data: AnyToml = ...
    _file_path: Path
    _section: list[str]

    # Initialiser
    def __init__(self, file_path: Path, **keywords: Any) -> None:
        """
        Store the path to the TOML file and the required section.

        :param file_path: The path to the file from which the settings are to
            be loaded.
        """

        super().__init__(**keywords)
        self._file_path = file_path

    # Public properties
    @property
    def file_path(self) -> Path:
        """
        Get the path to the file storing the settings.
        """

        return self._file_path

    @property
    def section(self) -> str:
        """
        Get the TOML path to the relevant section.
        """

        return ".".join(self._section)

    # Public methods
    def load(
        self,
        section: str = "",
        *,
        parse_float: Callable[[str], Any] = float,
        refresh: bool = False,
    ) -> AnyToml:
        """
        Load the TOML section into a Python object. A thin wrapper for the
        :py:func:`load` function.

        :param section: The path to the required attributes in the file.
        :param parse_float: A function that specifies the decimal conversion
            method. Defaults to ``float``.
        :param refresh: Whether the cached data should be refreshed by loading
            from the source file again. Defaults to False.

        :return: The Python object representing the relevant TOML section.

        :raise TOMLDecodeError: The file is not valid TOML.
        """

        # Set default value
        section = "" if section is ... else section
        parse_float = float if parse_float is ... else parse_float

        # Extract path
        section = section.split(".")
        self._section = [] if section == [""] else section

        # Load from file if the cache is empty or a refresh is forced
        if self._data is ... or refresh:
            # Read file as binary for cross-platform UTF-8 compatibility
            with open(self._file_path, mode="rb") as file:
                self._data = load(file, parse_float=parse_float)

        # Retrieve the section data
        settings = self._data
        for path in self._section:
            try:
                settings = settings[path]
            except AttributeError:
                raise AttributeError(
                    f"No attribute '{path}' found in {settings.keys()}.",
                )
        return settings

    # Special methods
    def __str__(self) -> str:
        """
        Return a readable string representation of the parser.
        """

        output = str(self._file_path)
        output += f": {self.section}" if self.section else ""
        return output
