import typing as T
from collections import defaultdict

from injector import Injector, InstanceProvider, Provider, Scope


def singletons_by_cls(injector: Injector, scope: type[Scope]) -> dict[type, Provider]:
    try:
        return injector.binder._bindings[scope].provider._instance._context
    except Exception:
        return {}


def singletons(
    injector: Injector, scope: type[Scope]
) -> dict[str, tuple[object, ...] | object]:
    """Get all singletons by class name."""
    singletons = singletons_by_cls(injector, scope)

    result = defaultdict(list)
    for cls, ston in singletons.items():
        if not isinstance(ston, InstanceProvider):
            continue
        result[cls.__name__].append(ston._instance)
    return {
        name: tuple(stons) if len(stons) > 1 else stons[0]
        for name, stons in result.items()
    }


class SingletonAccessor:
    def __init__(self, injector: Injector, scopes: tuple[type[Scope], ...]):
        self.__injector = injector
        self.__scopes = scopes
        self.__last_singletons_count = 0
        self.__last_singletons = {}

        # Hack: stop ipython constantly checking for non-existent vars and halting
        # my debugger
        self._ipython_canary_method_should_not_exist_ = True
        # Another ipython hack.
        self.__custom_documentations__ = {}

    def __get_singletons(self):
        s_by_cs = tuple(singletons_by_cls(self.__injector, s) for s in self.__scopes)
        singletons_count = sum(len(s_by_c) for s_by_c in s_by_cs)
        if singletons_count != self.__last_singletons_count:
            new_singletons_dict = {}
            for scope in self.__scopes:
                new_singletons_dict.update(singletons(self.__injector, scope))
            self.__last_singletons = new_singletons_dict
            self.__last_singletons_count = singletons_count
        return self.__last_singletons

    def keys(self) -> T.KeysView[str]:
        return self.__get_singletons().keys()

    def values(self) -> T.ValuesView[object]:
        return self.__get_singletons().values()

    def items(self) -> T.ItemsView[str, object]:
        return self.__get_singletons().items()

    def __contains__(self, item: str) -> bool:
        return item in self.__get_singletons()

    def __len__(self) -> int:
        return len(self.__get_singletons())

    def __iter__(self) -> T.Iterator[str]:
        return iter(self.__get_singletons().keys())

    def __getitem__(self, key: str) -> object:
        singletons = self.__get_singletons()
        if key in singletons:
            return singletons[key]
        raise KeyError

    def __getattr__(self, name: str) -> T.Any:
        singletons = self.__get_singletons()
        if name in singletons:
            return singletons[name]
        raise AttributeError
