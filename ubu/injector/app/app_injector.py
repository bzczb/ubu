from ubu.injector._api import APP_INJECTOR_FLAG, Injector, Module


class AppModule(Module):
    """Main application module configuring dependency injection bindings."""

    def __init__(self, injected_params: dict) -> None:
        super().__init__()


def create_app_injector(injected_params) -> Injector:
    """Create and configure the dependency injection container."""
    injector = Injector([AppModule(injected_params=injected_params)])
    setattr(injector, APP_INJECTOR_FLAG, True)
    return injector
