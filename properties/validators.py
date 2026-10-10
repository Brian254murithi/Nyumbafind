from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class ImageValidator:
    """Validate uploaded property/avatar images: type and size."""

    def __call__(self, value):
        if value is None:
            return
        content_type = getattr(value.file, "content_type", None)
        if content_type and content_type not in (
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/gif",
        ):
            raise ValidationError(
                "Unsupported image type. Use JPEG, PNG, WebP or GIF."
            )
        max_size = 5 * 1024 * 1024  # 5 MB
        if value.size > max_size:
            raise ValidationError(
                "Image is too large. Maximum file size is 5 MB."
            )


validate_upload = ImageValidator()


def validate_amenities(value):
    if not isinstance(value, list):
        raise ValidationError("Amenities must be a list of strings.")
    if len(value) > 20:
        raise ValidationError("Provide at most 20 amenities.")
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValidationError("Each amenity must be a non-empty string.")
        if len(item) > 60:
            raise ValidationError("Each amenity must be 60 characters or fewer.")
