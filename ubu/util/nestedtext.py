import datetime
import os
import typing as T
from functools import partial
from pathlib import Path, PurePath
from uuid import UUID

import nestedtext as nt
from cattrs.cols import is_namedtuple, namedtuple_unstructure_factory
from cattrs.converters import BaseConverter, Converter
from cattrs.strategies import configure_union_passthrough


def make_general_converter() -> BaseConverter:
    converter = Converter()

    # Handle string enums
    converter.register_unstructure_hook(
        str, lambda v: v if v.__class__ is str else v.value
    )

    # Handle paths
    converter.register_structure_hook(PurePath, lambda v, _: PurePath(v))
    converter.register_unstructure_hook(PurePath, lambda path: str(path))

    # Handle booleans
    converter.register_structure_hook(
        bool, lambda v, _: {'true': True, 'false': False}.get(v.lower())
    )
    converter.register_unstructure_hook(bool, lambda b: str(b).lower())

    # Handle UUIDs
    converter.register_structure_hook(UUID, lambda v, _: UUID(v))
    converter.register_unstructure_hook(UUID, lambda u: str(u))

    # Handle dates
    converter.register_structure_hook(
        datetime.date,
        lambda v, _: datetime.date.fromisoformat(v),
    )
    converter.register_unstructure_hook(
        datetime.date,
        lambda v: v.isoformat(),
    )
    converter.register_structure_hook(
        datetime.datetime,
        lambda v, _: datetime.datetime.fromisoformat(v),
    )
    converter.register_unstructure_hook(
        datetime.datetime,
        lambda v: v.isoformat(),
    )

    # Handle named tuples
    converter.register_structure_hook_factory(is_namedtuple)(
        partial(namedtuple_unstructure_factory, unstructure_to=tuple)
    )

    # Allow unions
    configure_union_passthrough(
        str | bool | int | float | bytes | datetime.datetime | datetime.date | None,
        converter,
    )

    return converter


general_converter = make_general_converter()


def sco_from_nt(nestedtext: str, config_cls: type):
    od = nt.loads(nestedtext)
    return general_converter.structure(od, config_cls)


def sco_from_file(filepath: str | Path, config_cls: type):
    return sco_from_nt(Path(filepath).read_text(), config_cls)


def config_to_nt(config: T.Any):
    config_dict = general_converter.unstructure_attrs_asdict(config)
    return nt.dumps(config_dict, indent=2)


def config_to_file(config: T.Any, filepath: str | Path):
    yaml = config_to_nt(config)
    with open(os.path.abspath(filepath), 'w', encoding='utf-8') as file:
        file.write(yaml)
