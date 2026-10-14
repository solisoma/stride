from typing import Protocol


class Provider(Protocol):
    def generate(self, instruction: str, evidence: list[dict]) -> dict: ...

