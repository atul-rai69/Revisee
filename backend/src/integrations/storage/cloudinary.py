from typing import BinaryIO

import cloudinary
import cloudinary.uploader

from src.core.config import Settings
from src.core.exceptions import ProviderUnavailableError
from src.integrations.storage.base import UploadedAsset


class CloudinaryStorageProvider:
    def __init__(self, settings: Settings) -> None:
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )

    def upload(self, file: BinaryIO, resource_type: str) -> UploadedAsset:
        try:
            result = cloudinary.uploader.upload(file, resource_type=resource_type)
        except Exception as exc:
            raise ProviderUnavailableError("Media storage is unavailable") from exc
        return UploadedAsset(
            url=result["secure_url"],
            public_id=result["public_id"],
            resource_type=resource_type,
        )

    def delete(self, public_id: str, resource_type: str) -> None:
        try:
            cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        except Exception as exc:
            raise ProviderUnavailableError("Media cleanup failed") from exc
