import typing as T

import attr

from ubu.injector._api import app_scope


@attr.s(auto_attribs=True, frozen=True)
class Feature:
    """Class representing a feature."""

    name: str
    description: str
    check: T.Callable[[], bool]


@app_scope
class Features:
    def __init__(self):
        """Initialize the Features singleton."""
        self._features: dict[str, Feature] = {}
        self._availability: dict[str, bool] = {}

    def register_feature(self, feature: Feature) -> None:
        """Register a feature."""
        if feature.name in self._features:
            return  # Silently ignore if already registered
        self._features[feature.name] = feature
        self._availability[feature.name] = feature.check()

    def is_feature_available(self, feature: Feature) -> bool:
        """Check if a feature is available."""
        if feature.name not in self._features:
            self.register_feature(feature)
        return self._availability.get(feature.name, False)
