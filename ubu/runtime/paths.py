import logging
import os
import shutil
from pathlib import Path
from uuid import uuid4

import attr
from platformdirs import PlatformDirs

from ubu.injector._api import app_scope, inject
from ubu.runtime.app_info import AppInfo

log = logging.getLogger(__name__)


@app_scope
@attr.s(init=False)
class RuntimePaths:
    @inject
    def __init__(self, app_info: AppInfo):
        self.__attrs_init__()
        self.platform_dirs = PlatformDirs(
            appname=app_info.name,
            appauthor=app_info.author,
            roaming=True,
            ensure_exists=True,
        )
        platform_dirs = self.platform_dirs
        self.temp_path = platform_dirs.user_runtime_path

        if os.environ.get('PYTEST_VERSION'):
            # pytest is running
            test_uuid = uuid4()
            self.data_path = self.temp_path / f'test-data-{test_uuid}'
            self.cache_path = self.temp_path / f'test-cache-{test_uuid}'
            self.log_path = self.temp_path / f'test-log-{test_uuid}'
        else:
            self.data_path = platform_dirs.user_data_path
            self.cache_path = platform_dirs.user_cache_path
            self.log_path = platform_dirs.user_log_path

        additional_paths = {
            'plugin': 'Plugins',
            'pack': 'Packs',
        }

        for attr_name, dir_name in additional_paths.items():
            setattr(self, f'{attr_name}_path', self.data_path / dir_name)
            getattr(self, f'{attr_name}_path').mkdir(parents=True, exist_ok=True)

        self.cache_path.mkdir(parents=True, exist_ok=True)
        self.log_path.mkdir(parents=True, exist_ok=True)

    data_path: Path = attr.ib(factory=Path)
    cache_path: Path = attr.ib(factory=Path)
    temp_path: Path = attr.ib(factory=Path)
    log_path: Path = attr.ib(factory=Path)

    plugin_path: Path = attr.ib(default=None)
    pack_path: Path = attr.ib(default=None)

    platform_dirs: PlatformDirs = attr.ib(init=False)

    @property
    def app_db_path(self) -> Path:
        return self.data_path / 'app.db'

    def clear_temp(self) -> None:
        for item in self.temp_path.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
            except Exception:
                log.warning(f'Could not delete temp item: {item}', exc_info=True)
