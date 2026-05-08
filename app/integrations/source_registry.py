from collections.abc import Callable

from app.integrations.mock_tracking_source import MockTrackingSource
from app.integrations.tracking_source import NullTrackingSource, TrackingRequest, TrackingSource


class TrackingSourceRegistry:
    def __init__(self):
        self._entries: list[tuple[Callable[[TrackingRequest], bool], TrackingSource]] = []
        self._fallback = NullTrackingSource()
        self.register(
            lambda request: bool(request.trade_url and request.trade_url.startswith("mock://")),
            MockTrackingSource(),
        )

    def register(self, matcher: Callable[[TrackingRequest], bool], source: TrackingSource) -> None:
        self._entries.append((matcher, source))

    def resolve(self, request: TrackingRequest) -> TrackingSource:
        for matcher, source in self._entries:
            if matcher(request):
                return source
        return self._fallback
