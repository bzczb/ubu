"""
Define custom scopes for dependency injection here.
Using a separate file avoids circular import.
"""

import logging

from injector import Injector, InstanceProvider, ScopeDecorator, SingletonScope

log = logging.getLogger(__name__)


class ScopeGivenWrongInjectorException(Exception):
    """Exception raised when a scope is given an injector of the wrong type."""


class TeardownSingletonScope(SingletonScope):
    """Scope that detects and runs teardown handlers on objects."""

    def teardown(self):
        """Tear down the scope, cleaning up instances."""

        # Tear down in reverse order of instantiation.
        for provider in reversed(self._context.values()):
            if not isinstance(provider, InstanceProvider):
                continue
            instance = provider._instance
            if hasattr(instance, 'teardown'):
                log.debug('Tearing down %r', instance)
                instance.teardown()


APP_INJECTOR_FLAG = '__APP_INJECTOR__'


class AppScope(TeardownSingletonScope):
    """Scope for singleton objects in the app; main process only."""

    def __init__(self, injector: Injector) -> None:
        if not getattr(injector, APP_INJECTOR_FLAG, False):
            raise ScopeGivenWrongInjectorException
        super().__init__(injector)


app_scope = ScopeDecorator(AppScope)


JOB_INJECTOR_FLAG = '__JOB_INJECTOR__'


class JobScope(TeardownSingletonScope):
    """Scope for singleton objects tied to a job."""

    def __init__(self, injector: Injector) -> None:
        if not getattr(injector, JOB_INJECTOR_FLAG, False):
            raise ScopeGivenWrongInjectorException
        super().__init__(injector)

    def _get_instance(self, key, provider, injector):
        # Override default behavior, which tries to create an instance in the
        # parent injector.
        return provider.get(injector)


job_scope = ScopeDecorator(JobScope)


PROCESS_WORKER_INJECTOR_FLAG = '__PROCESS_WORKER_INJECTOR__'


class ProcessWorkerScope(TeardownSingletonScope):
    """Scope for singleton objects that exist in a process worker."""

    def __init__(self, injector: Injector) -> None:
        if not getattr(injector, PROCESS_WORKER_INJECTOR_FLAG, False):
            raise ScopeGivenWrongInjectorException
        super().__init__(injector)


process_worker_scope = ScopeDecorator(ProcessWorkerScope)
