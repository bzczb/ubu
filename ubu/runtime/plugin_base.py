"""
Base class for all plugins.
See src/ubuplugin/builtin/__init__.py for the builtin plugin.
"""

import typing as T
from uuid import UUID

import attr

from ubu.injector._api import inject
from ubu.runtime.extensions import Extensions


@attr.s(auto_attribs=True, frozen=True)
class PendingExtension:
    obj: T.Any
    endpoint_uuid: UUID | tuple[UUID, ...] = ()


class PluginMeta(type):
    def __init__(cls, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        cls.included: list[PendingExtension] = []

    def include(cls, obj):
        cls.included.append(PendingExtension(obj=obj))
        return obj


class PluginBase(metaclass=PluginMeta):
    # populated from .nt file when loading plugin
    __PACK__: T.Any  # 'T.ClassVar[Pack]'

    # packages to walk and get all the submodules of
    walk_packages: T.ClassVar[tuple[str, ...]] = ()

    # packages to import without walking
    import_packages: T.ClassVar[tuple[str, ...]] = ()

    # the plugin's extensions
    included: T.ClassVar[list[PendingExtension]]

    @inject
    def __init__(self, extensions: Extensions):
        for pending in self.included:
            extensions.add_extension(self, pending.obj, pending.endpoint_uuid)

    @property
    def pack_uuid(self) -> UUID:
        return self.__PACK__.uuid

    @property
    def pack_name(self) -> str:
        return self.__PACK__.name
