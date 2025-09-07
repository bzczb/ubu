import attr


@attr.define
class AppInfo:
    name: str
    version: str
    author: str | None = None
    description: str | None = None
