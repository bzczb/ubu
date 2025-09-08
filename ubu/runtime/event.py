"""
App-wide event queue and event definitions.
"""

import logging
from enum import IntEnum, auto, unique

from eventpy.eventqueue import EventQueue as OriginalEventQueue

from ubu.injector._api import app_scope

log = logging.getLogger(__name__)


class MissingMethodError(Exception):
    pass


@app_scope
class EventQueue(OriginalEventQueue):
    def bind_listener(self, obj, events_list: 'list[Event]'):
        handles = []
        events_set = set(events_list)

        for e in events_set:
            methodname = f'on_event_{e.name.lower()}'

            method_on_obj = getattr(obj, methodname, None)

            # We can have multiple binding groups.
            # The generate popup has both a resize handler and generate status handlers.
            # These are attached with different code.

            if method_on_obj:
                handle = self.appendListener(e, method_on_obj)
                handles.append((e, handle))
            else:
                raise MissingMethodError(f'{methodname}()')

        return handles

    def unbind_listener(self, handles):
        for e, h in handles:
            self.removeListener(e, h)


@unique
class Event(IntEnum):
    EXTENSION_REGISTERED = auto()  # dispatch, arg is (endpoint uuid, extension | obj)

    PLUGIN_LOADED_ONE = auto()  # dispatch, arg is plugin
    PLUGIN_LOADED_ALL = auto()  # dispatch, arg is plugin manager

    FINISHED_STARTUP = auto()  # dispatch

    JOB_START = auto()  # dispatch, arg is JobStatus
    JOB_STATUS = auto()  # enqueue, arg is JobStatus

    SETTINGS_CHANGE = auto()  # enqueue

    DB_UPDATE = auto()  # enqueue UNUSED
    PACK_TREE_UPDATE = auto()  # enqueue, no args
    OBJECT_CHANGE = auto()  # enqueue, arg is (ObjectChangeEvent)

    STATUS_POPUP = auto()  # enqueue, arg is (status type, message)
    HIDEABLE_WARNING_POPUP = auto()  # enqueue, arg is (message code, message)
