# Re-export some stuff from injector:
import typing as __T

from injector import (
    AssistedBuilder,
    ClassAssistedBuilder,
    ClassProvider,
    Injector,
    InstanceProvider,
    Module,
    Provider,
    Scope,
    ScopeDecorator,
    SingletonScope,
    inject,
    provider,
)

from .scopes import (
    APP_INJECTOR_FLAG,
    JOB_INJECTOR_FLAG,
    PROCESS_WORKER_INJECTOR_FLAG,
    AppScope,
    JobScope,
    ProcessWorkerScope,
    TeardownSingletonScope,
    app_scope,
    job_scope,
    process_worker_scope,
)
from .singleton_accessor import SingletonAccessor

if __T.TYPE_CHECKING:

    class BaseGenericAlias:
        pass

else:
    from typing import _BaseGenericAlias as BaseGenericAlias

__all__ = [
    'AssistedBuilder',
    'ClassAssistedBuilder',
    'ClassProvider',
    'Injector',
    'InstanceProvider',
    'Module',
    'Provider',
    'Scope',
    'ScopeDecorator',
    'SingletonScope',
    'inject',
    'provider',
    'APP_INJECTOR_FLAG',
    'JOB_INJECTOR_FLAG',
    'PROCESS_WORKER_INJECTOR_FLAG',
    'AppScope',
    'JobScope',
    'ProcessWorkerScope',
    'TeardownSingletonScope',
    'app_scope',
    'job_scope',
    'process_worker_scope',
    'SingletonAccessor',
    'BaseGenericAlias',
    'BaseGenericAlias',
]
