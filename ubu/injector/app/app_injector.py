from ubu.injector._api import APP_INJECTOR_FLAG, Injector, Module, app_scope, provider
from ubu.runtime._api import AppInfo


class AppModule(Module):
    """Main application module configuring dependency injection bindings."""

    def __init__(self, injected_params: dict) -> None:
        super().__init__()

    @app_scope
    @provider
    def provide_app_info(self) -> AppInfo:
        """Provide default application information."""
        return AppInfo(
            name='Ubu',
            version='0.0.1',
            author='bzczb',
            description='Ubu application framework -- default AppInfo',
        )


def create_app_injector(injected_params) -> Injector:
    """Create and configure the dependency injection container."""
    injector = Injector([AppModule(injected_params=injected_params)])
    setattr(injector, APP_INJECTOR_FLAG, True)
    return injector
