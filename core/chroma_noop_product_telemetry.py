"""ChromaDB 0.5 产品遥测空实现：避免与新版 posthog 的 capture() 签名不兼容导致控制台刷屏。"""

from overrides import override

from chromadb.config import System
from chromadb.telemetry.product import ProductTelemetryClient, ProductTelemetryEvent


class NoOpProductTelemetry(ProductTelemetryClient):
    def __init__(self, system: System) -> None:
        super().__init__(system)

    @override
    def capture(self, event: ProductTelemetryEvent) -> None:  # noqa: ARG002
        return
