import attr


@attr.define(frozen=True)
class UbuSettings:
    __settings_key__ = 'ubu'

    debug: bool = attr.ib(default=False)
