"""
Loads plugin code into sys.modules and instantiate the plugin class.
"""

import importlib.util
import logging
import pkgutil
import sys
import typing as T
from pathlib import Path
from uuid import UUID

from ubu.injector._api import Injector, app_scope, inject
from ubu.runtime.event import Event, EventQueue
from ubu.runtime.plugin_base import PluginBase

if T.TYPE_CHECKING:
    from ubu.runtime.pack import Pack

log = logging.getLogger(__name__)


class LoadingProcess:
    def __init__(self, pack: Pack) -> None:
        md = pack.md
        self.pack_name: str = md.name
        self.pack_uuid: UUID = md.uuid
        if not md.is_plugin:
            raise ValueError(f'Pack "{self.pack_name}" is not a plugin pack.')

        base_path: Path | None = pack.path
        if base_path is None:
            raise ValueError(f'Pack "{self.pack_name}" has no base_path set.')
        self.base_path = base_path

        if md.plugin is None:
            raise ValueError(
                f'Pack "{self.pack_name}" has no plugin configuration set.'
            )

        mod_name: str | None = md.plugin.module_name
        if mod_name is None:
            raise ValueError(f'Pack "{self.pack_name}" has no plugin module_name set.')
        self.mod_name = mod_name
        self.qmod_name = f'ubuplugin.{self.mod_name}'

        self.mod_path = self.base_path / '__init__.py'
        if not self.mod_path.exists():
            raise FileNotFoundError(
                f'Pack "{self.pack_name}" plugin module not found at {self.mod_path}'
            )

        self.log_prefix = f'"{self.pack_name}" '
        log.info(f'{self.log_prefix}loading')

    def is_already_loaded(self) -> bool:
        if installed_module := sys.modules.get(self.qmod_name) is not None:
            plugin_class = getattr(installed_module, '__plugin__', None)
            if plugin_class is None or not issubclass(plugin_class, PluginBase):
                raise ValueError(
                    f'Plugin "{self.pack_name}" with module "{self.mod_name}" has no valid "__plugin__", expected PluginBase subclass'
                )
            if plugin_class.pack_uuid == self.pack_uuid:
                raise ValueError(
                    f'Plugin "{self.pack_name}" with module "{self.mod_name}" is already loaded, but the UUID does not match the existing plugin.'
                )
            return True
        return False

    def run_mod(self) -> type[PluginBase]:
        spec = importlib.util.spec_from_file_location(
            self.qmod_name, self.mod_path, submodule_search_locations=[]
        )

        if not spec or not spec.loader:
            raise ImportError(f'Could not load plugin module from {self.mod_path}')

        plugin_mod = importlib.util.module_from_spec(spec)
        # plugin_mod.__path__ = [str(self.base_path)]
        sys.modules[self.qmod_name] = plugin_mod
        setattr(sys.modules['ubuplugin'], self.mod_name, plugin_mod)
        spec.loader.exec_module(plugin_mod)
        plugin_class = T.cast(type[PluginBase], getattr(plugin_mod, '__plugin__', None))

        if not issubclass(plugin_class, PluginBase):
            raise TypeError(
                f'Pack "{self.pack_name}" has no valid "__plugin__", '
                f'expected PluginBase subclass, got {plugin_class}'
            )

        for pkg_path in plugin_class.walk_packages:
            sub_mod = importlib.import_module(self.qmod_name + '.' + pkg_path)
            for _, sub_sub_mod_name, _ in pkgutil.walk_packages(
                sub_mod.__path__, sub_mod.__name__ + '.'
            ):
                # execute every module to set up the plugin
                # this is a cheap way to do something like Venusian
                # or spring boot's component scan
                if sub_sub_mod_name.split('.')[-1].startswith('_'):
                    continue
                importlib.import_module(sub_sub_mod_name)

        for pkg_path in plugin_class.import_packages:
            sub_mod = importlib.import_module(self.qmod_name + '.' + pkg_path)

        return plugin_class


@app_scope
class PluginLoader:
    @inject
    def __init__(self, eq: EventQueue, injector: Injector) -> None:
        self._eq = eq
        self._injector = injector

    def load(self, pack: Pack) -> None:
        loading = LoadingProcess(pack)
        log_prefix = loading.log_prefix
        if loading.is_already_loaded():
            log.debug(f'{log_prefix}already loaded, skipping')
            return
        log.info(f'{log_prefix}loading')

        plugin_class = loading.run_mod()
        plugin_class.__PACK__ = pack

        log.debug(f'{log_prefix}startup')
        pack.plugin = self._injector.create_object(plugin_class)

        self._eq.dispatch(Event.PLUGIN_LOADED_ONE, pack)

        log.debug(f'{log_prefix}loaded successfully')
