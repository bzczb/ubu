"""
Top-level storage container for domain objects.
Can be exported to a .zip file.
"""

import datetime
import logging
import typing as T
from pathlib import Path
from uuid import UUID

import attr

from ubu.util.nestedtext import general_converter, nt_loads

if T.TYPE_CHECKING:
    from ubu.runtime.plugin_base import PluginBase

PACK_V1_FORMAT = 'ubu-pack-v1'


@attr.define(frozen=True)
class PackDependency:
    uuid: UUID = attr.ib()
    minimum_version: int = attr.ib()


@attr.define(frozen=True)
class PluginMD:
    module_name: str = attr.ib()


@attr.define(frozen=True)
class PackMD:
    """
    Metadata about a pack which is distributed in the pack itself.
    It should be in the root of the archive and named `ubupack.nt`.
    """

    format: str = attr.ib()
    """
    Format version of the pack metadata.
    Currently, the only supported value is 'ubu-pack-v1'.
    """
    name: str = attr.ib()
    """
    Name of the pack.
    """
    author: str = attr.ib()
    """
    Author of the pack.
    """
    date_created: datetime.date = attr.ib()
    """
    Date the pack was created.
    Should be updated on each release.
    """
    version: int = attr.ib()
    """
    Version number of the pack.
    Should be incremented on each release, starting from 1.
    """
    uuid: UUID = attr.ib()
    """
    Unique UUID of the pack.
    Should be generated randomly once and never changed.
    """
    startup_behavior: T.Literal['reload', 'check', 'no_reload'] = attr.ib(
        default='no_reload'
    )
    """
    Startup behavior.
    - reload
        Always reload the pack into the database at startup.
        Delete all objects in the pack and then load them again.
        Useful for development.
    - check
        Compare objects in the DB with objects.nt.
        Update if different.
    - no_reload
        Leave objects in the DB alone.
    """
    is_plugin: bool = attr.ib(default=False)
    """
    Whether this pack is a plugin.
    Plugins contain code and are loaded at startup.
    """
    plugin: PluginMD | None = attr.ib(default=None)
    """
    Configuration present if this pack is a plugin.
    """
    dependencies: list[PackDependency] = attr.ib(factory=list)
    """
    Dependencies on other packs.
    Packs in this list will be installed before this pack is installed.
    """


@attr.define(frozen=True)
class PackDBMD:
    """
    Metadata about a pack which is stored in the database.
    """

    id: int = attr.ib()
    """
    Database ID of the pack.
    """
    uuid: UUID = attr.ib()
    """
    Unique UUID of the pack.
    Should match PackMD.uuid.
    """
    version: int = attr.ib()
    """
    Version number of the pack.
    Should match PackMD.version.
    """
    name: str = attr.ib()
    """
    Name of the pack. Should match PackMD.name.
    Makes examining the DB easier.
    """
    path: Path = attr.ib()
    """
    Path to the directory of the unzipped pack on disk.
    Makes debugging easier.
    """
    objects_installed: bool = attr.ib()
    """
    Object install has completed since the last version update.
    """


@attr.define
class Pack:
    path: Path = attr.ib()
    """
    Path to the directory of the unzipped pack on disk.
    """
    md: PackMD = attr.ib(init=False)
    """
    Pack metadata (ubupack.nt).
    """
    db_md: PackDBMD = attr.ib(init=False)
    """
    Pack metadata stored in the database.
    """
    plugin: 'PluginBase | None' = attr.ib(default=None, init=False)
    """
    If this is a plugin pack, the instantiated plugin object.
    """
    uninstalled: bool = attr.ib(default=False, init=False)
    """
    This pack has been uninstalled.
    """

    @property
    def id(self) -> int:
        if not hasattr(self, 'db_md'):
            raise RuntimeError('Pack ID is not set')
        return self.db_md.id


def load_pack_md(path: Path) -> PackMD:
    """
    Load pack metadata from a path.
    The path should point to a `ubupack.nt` file.
    """
    logging.debug(f'Loading pack metadata from {path}')
    raw_data = nt_loads(path.read_text())
    if raw_data['format'] != PACK_V1_FORMAT:
        raise ValueError(f'Unsupported pack format: {raw_data["format"]}')
    return general_converter.structure(raw_data, PackMD)
