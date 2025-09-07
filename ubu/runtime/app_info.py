import attr


@attr.define(frozen=True)
class AppInfo:
    name: str
    version: str
    author: str | None = None
    description: str | None = None
