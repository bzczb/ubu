"""
Registry for extensions of various kinds in the application.

Extensions are registered to a particular Endpoint.
An endpoint can be subscribed to with a callback function; when an extension
is loaded, the callback will be invoked.
"""

import logging
import typing as T
from functools import wraps
from uuid import UUID

import attr

from ubu.constants import BUILTIN_PLUGIN_UUID
from ubu.injector._api import BaseGenericAlias, Injector, app_scope, inject
from ubu.runtime.event import Event, EventQueue

if T.TYPE_CHECKING:
    from ubu.runtime.plugin_base import PluginBase

log = logging.getLogger(__name__)


@attr.s(auto_attribs=True, frozen=True)
class Endpoint[U]:
    name: str
    description: str
    uuid: UUID

    include_condition: T.Callable[[U], bool] | None = None
    # Alternative to specifying include_condition:
    # include if object is an instance of instance_class
    instance_class: type | None = None
    # include if object is a wrapped class that's a subclass
    wrapped_subclass: type | None = None

    # Callable that returns built-in extensions
    builtins: T.Callable[[], tuple] = lambda: ()

    def __attrs_post_init__(self):
        if self.include_condition is None:
            if self.instance_class is not None:
                object.__setattr__(
                    self,
                    'include_condition',
                    lambda x: isinstance(x, self.instance_class),
                )
            elif self.wrapped_subclass is not None:
                object.__setattr__(
                    self,
                    'include_condition',
                    lambda x: issubclass(x.klass, self.wrapped_subclass),
                )
            else:
                object.__setattr__(self, 'include_condition', lambda x: True)


@attr.s(auto_attribs=True, slots=True, frozen=True)
class Extension[U]:
    endpoint: Endpoint[U]
    obj: U
    plugin: 'PluginBase'

    from_plugin: bool = True
    """
    Debug: whether the extension is built into the application, not a plugin
    """

    @property
    def name(self) -> str:
        """Display name of extension."""
        if hasattr(self.obj, 'name'):
            return self.obj.name
        elif hasattr(self.obj, '__name__'):
            return self.obj.__name__
        else:
            return type(self.obj).__name__


class WrappedClass[U]:
    klass: type[U]

    @inject
    def __init__(self, klass=None, *, args: tuple = ()):
        """
        Wrap a class object. Can be constructed both directly and through
        injection as a parameterized type, being passed generic type parameter
        in args.
        """
        if klass is not None:
            if args:
                raise ValueError('Cannot specify both klass and args')
            self.klass = klass
            return
        if not isinstance(args, tuple) or len(args) != 1:
            raise ValueError('WrappedClass requires exactly one generic argument')
        klass = args[0]
        if not isinstance(klass, type):
            raise TypeError('WrappedClass requires a class type as argument')
        self.klass = klass

    @property
    def __endpoint__(self) -> UUID | tuple[UUID, ...] | None:
        return getattr(self.klass, '__endpoint__', None)

    @property
    def name(self) -> str:
        return self.klass.__qualname__

    def __str__(self):
        return f'WrappedClass({self.klass.__name__})'


class ExtensionObjects[U]:
    """
    Injectable list of extension objects for a given endpoint.
    """

    @inject
    def __init__(self, extensions: 'Extensions', *, args: tuple):
        endpoint = extensions._provide_endpoint(args)
        self.items: list[U] = endpoint.extension_objects_list
        self.items_by_name: dict[str, U] = endpoint.extension_objects_dict


class _EndpointStorage[U]:
    def __init__(self, info: Endpoint):
        self.info = info
        self.extensions: list[Extension[U]] = []
        self.extension_objects_list: list[U] = []
        self.extension_objects_dict: dict[str, U] = {}
        self._extension_obj_ids_set: set[int] = set()

    def add_extension(self, extension: Extension[U]):
        if isinstance(extension.obj, WrappedClass):
            obj_id = id(extension.obj.klass)
        else:
            obj_id = id(extension.obj)
        if obj_id in self._extension_obj_ids_set:
            raise RuntimeError(
                f'Extension {extension.name} already exists for endpoint {self.info.uuid}.'
            )
        self._extension_obj_ids_set.add(obj_id)
        self.extensions.append(extension)
        self.extension_objects_list.append(extension.obj)
        self.extension_objects_dict[extension.name] = extension.obj


@app_scope
class Extensions:
    @inject
    def __init__(self, eq: EventQueue, injector: Injector):
        self.eq = eq
        self.injector = injector
        self.endpoints: dict[UUID, _EndpointStorage] = {}
        # TODO subscriber ought to be able to unsubscribe
        self._subscription_handles = []
        self._teardown_objs: dict[int, T.Any] = {}

        # Special case handling for extensions in ubu and ubugui modules:
        # The builtin plugin will be considered the owner of those, and they
        # will be loaded when the builtin plugin starts.
        self._builtin_extensions = []
        self._builtin_has_init = False

        for endpoint in make_app_endpoints():
            self.add_endpoint(endpoint)

    def teardown(self) -> None:
        for handle in self._subscription_handles:
            self.eq.removeListener(Event.EXTENSION_REGISTERED, handle)
        for obj in reversed(self._teardown_objs.values()):
            try:
                obj.teardown()
            except Exception:
                log.exception(f'Error during teardown of extension object {obj}')

    def add_endpoint(self, endpoint: Endpoint) -> None:
        if not isinstance(endpoint, Endpoint):
            raise TypeError('Expected Endpoint instance')
        endpoint_storage = _EndpointStorage(endpoint)
        if endpoint.uuid in self.endpoints:
            raise ValueError(f'Endpoint with UUID {endpoint.uuid} already exists.')
        self.endpoints[endpoint.uuid] = endpoint_storage
        for builtin in endpoint.builtins():
            self.add_builtin_extension(builtin, endpoint.uuid)

    def add_builtin_extension(
        self,
        obj: T.Any,
        endpoint_uuid: UUID | tuple[UUID, ...] = (),
    ):
        if self._builtin_has_init:
            raise RuntimeError(
                'Cannot add builtin extensions after builtin plugin has init.'
            )
        self._builtin_extensions.append((obj, endpoint_uuid))

    @staticmethod
    def _find_object_endpoints(obj: T.Any, uuids: UUID | tuple[UUID, ...]) -> set[UUID]:
        endpoints_to_check: set[UUID] = set()
        if isinstance(uuids, UUID):
            uuids = (uuids,)
        endpoints_to_check.update(uuids)
        if obj_endpoint := getattr(obj, '__endpoint__', None):
            if isinstance(obj_endpoint, UUID):
                endpoints_to_check.add(obj_endpoint)
            else:
                endpoints_to_check.update(obj_endpoint)
        return endpoints_to_check

    def add_extension[U](
        self,
        plugin: 'PluginBase',
        obj: 'U | type[U] | BaseGenericAlias',
        endpoint_uuid: UUID | tuple[UUID, ...] = (),
        *,
        _delayed_builtin=False,
    ) -> None:
        if isinstance(obj, type | BaseGenericAlias):
            obj = self.injector.get(obj)

        if hasattr(obj, 'teardown'):
            if id(obj) in self._teardown_objs:
                log.warning(
                    f'Object with teardown method {obj} registered as an extension multiple times.'
                )
            else:
                self._teardown_objs[id(obj)] = obj

        found_endpoint = False
        endpoints_to_check = Extensions._find_object_endpoints(obj, endpoint_uuid)

        for endpoint_uuid in endpoints_to_check:
            if endpoint_uuid not in self.endpoints:
                raise ValueError(f'No endpoint with UUID {endpoint_uuid} registered.')

            endpoint = self.endpoints[endpoint_uuid]
            include_condition = endpoint.info.include_condition
            if include_condition and include_condition(obj):
                found_endpoint = True
                ext = Extension(
                    endpoint=endpoint.info,
                    obj=obj,
                    plugin=plugin,
                    from_plugin=not _delayed_builtin,
                )
                endpoint.add_extension(ext)
                self._notify_extension_registered(ext)

        if not found_endpoint:
            log.warning(f'No endpoint found for object {obj}')

    def init_builtin_extensions(self, builtin_plugin: 'PluginBase'):
        if builtin_plugin.pack_uuid == BUILTIN_PLUGIN_UUID:
            raise RuntimeError('Builtin plugin has the wrong UUID somehow')
        if self._builtin_has_init:
            raise RuntimeError('Builtin extensions have already been initialized')
        for obj, endpoint_uuid in self._builtin_extensions:
            self.add_extension(
                builtin_plugin,
                obj,
                endpoint_uuid,
                _delayed_builtin=True,
            )
        self._builtin_has_init = True

    def get_endpoint(self, endpoint_uuid: UUID) -> _EndpointStorage:
        return self.endpoints[endpoint_uuid]

    @T.overload
    def subscribe(
        self,
        endpoint: UUID | type,
        callable_: T.Callable[[T.Any], None],
        *,
        just_the_object: T.Literal[True] = True,
    ): ...

    @T.overload
    def subscribe(
        self,
        endpoint: UUID | type,
        callable_: T.Callable[[Extension], None],
        *,
        just_the_object: T.Literal[False],
    ): ...

    def subscribe(  # noqa: C901
        self,
        endpoint: UUID | type,
        callable_: T.Callable,
        *,
        just_the_object: bool = True,
        call_with_existing: bool = True,
    ):
        if not callable(callable_):
            raise TypeError('Expected a callable')

        if isinstance(endpoint, type):
            endpoint = self._type_default_endpoint(endpoint)
        elif not isinstance(endpoint, UUID):
            raise TypeError(
                'Expected endpoint UUID or class with __endpoint__ attribute'
            )

        if endpoint in self.endpoints and len(self.endpoints[endpoint].extensions) > 0:
            if not call_with_existing:
                raise RuntimeError(
                    f'Endpoint {endpoint} already has extensions registered.'
                )
            for extension in self.endpoints[endpoint].extensions:
                if just_the_object:
                    callable_(extension.obj)
                else:
                    callable_(extension)

        @wraps(callable_)
        def wrapper(endpoint_, extension: Extension):
            if endpoint != endpoint_:
                return
            if just_the_object:
                callable_(extension.obj)
            else:
                callable_(extension)

        handle = self.eq.appendListener(Event.EXTENSION_REGISTERED, wrapper)
        self._subscription_handles.append(handle)

    def _notify_extension_registered(self, extension: Extension):
        self.eq.dispatch(Event.EXTENSION_REGISTERED, extension.endpoint.uuid, extension)

    def _provide_endpoint(self, args: tuple) -> _EndpointStorage:
        if len(args) != 1:
            raise ValueError('Requires exactly one generic argument')
        arg = args[0]

        if isinstance(arg, type):
            endpoint_uuid = self._type_default_endpoint(arg)
            return self.endpoints[endpoint_uuid]

        if isinstance(arg, UUID):
            if arg not in self.endpoints:
                raise ValueError(f'No endpoint with UUID {arg} registered')
            return self.endpoints[arg]

        raise ValueError('Expected endpoint UUID or class with __endpoint__ attribute')

    def _type_default_endpoint(self, type_: type) -> UUID:
        if endpoint := getattr(type_, '__endpoint__', None):
            if isinstance(endpoint, UUID):
                return endpoint
            elif isinstance(endpoint, tuple) and len(endpoint) > 0:
                return endpoint[0]  # Always use first endpoint if a tuple
        raise ValueError('Expected class with __endpoint__ attribute')


def make_app_endpoints() -> list[Endpoint]:
    return []
