from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class UploadedAsset:
    url: str
    public_id: str
    resource_type: str


class StorageProvider(Protocol):
    def upload(self, file: BinaryIO, resource_type: str) -> UploadedAsset:
        ...

    def delete(self, public_id: str, resource_type: str) -> None:
        ...
