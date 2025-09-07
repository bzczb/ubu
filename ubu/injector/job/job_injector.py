from ubu.injector._api import JOB_INJECTOR_FLAG, Injector, Module


class JobModule(Module):
    def __init__(self) -> None:
        super().__init__()


def create_job_injector(injector: Injector) -> Injector:
    module: JobModule = JobModule()
    job_injector = injector.create_child_injector([module])
    setattr(job_injector, JOB_INJECTOR_FLAG, True)
    return job_injector
