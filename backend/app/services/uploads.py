from __future__ import annotations

import io

from PIL import Image, ImageOps


MAX_IMAGE_PIXELS = 40_000_000


def sanitize_image_upload(content: bytes, suffix: str) -> tuple[bytes, str]:
    """Decode, orient and re-encode images, dropping metadata and unsafe modes."""
    with Image.open(io.BytesIO(content)) as source:
        source.load()
        if source.width * source.height > MAX_IMAGE_PIXELS:
            raise ValueError("Image dimensions exceed the safe processing limit")
        image = ImageOps.exif_transpose(source)
        output = io.BytesIO()
        if suffix == ".png":
            image.convert("RGBA" if "A" in image.getbands() else "RGB").save(output, format="PNG", optimize=True)
            return output.getvalue(), ".png"
        if "A" in image.getbands():
            rgba = image.convert("RGBA")
            background = Image.new("RGB", image.size, "white")
            background.paste(rgba, mask=rgba.getchannel("A"))
            cleaned = background
        else:
            cleaned = image.convert("RGB")
        cleaned.save(output, format="JPEG", optimize=True)
        return output.getvalue(), ".jpg"
