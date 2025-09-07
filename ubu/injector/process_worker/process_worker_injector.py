from ubu.injector._api import PROCESS_WORKER_INJECTOR_FLAG, Injector, Module


class ProcessWorkerModule(Module):
    def __init__(self) -> None:
        super().__init__()


def create_process_worker_injector() -> Injector:
    injector = Injector([ProcessWorkerModule()])
    setattr(injector, PROCESS_WORKER_INJECTOR_FLAG, True)
    return injector
