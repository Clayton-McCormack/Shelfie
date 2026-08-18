"""Build compact, numbered contact sheets from detected book regions."""

from dataclasses import dataclass
from io import BytesIO
from math import ceil
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from .detect import BookBox


# One VLM request processes a batch rather than one HTTP call per spine. Eight
# crops fit comfortably in a 4-by-2 grid while retaining readable spine text.
CROPS_PER_SHEET = 8
COLUMNS = 4
CELL_WIDTH = 260
CELL_HEIGHT = 460
LABEL_HEIGHT = 36
JPEG_QUALITY = 85


@dataclass(frozen=True)
class ContactSheet:
    """One JPEG batch and the global crop indices represented by its cells."""

    indices: tuple[int, ...]
    image_bytes: bytes


def create_contact_sheets(image_path: str | Path, boxes: tuple[BookBox, ...]) -> tuple[ContactSheet, ...]:
    """Crop detected regions and batch them into numbered JPEG contact sheets."""
    if not boxes:
        return ()

    with Image.open(image_path) as opened:
        source = opened.convert('RGB')
        sheets = []

        for start in range(0, len(boxes), CROPS_PER_SHEET):
            batch = boxes[start : start + CROPS_PER_SHEET]
            rows = ceil(len(batch) / COLUMNS)
            canvas = Image.new('RGB', (COLUMNS * CELL_WIDTH, rows * CELL_HEIGHT), 'white')
            draw = ImageDraw.Draw(canvas)
            indices = []

            for offset, box in enumerate(batch):
                index = start + offset + 1
                column = offset % COLUMNS
                row = offset // COLUMNS
                x = column * CELL_WIDTH
                y = row * CELL_HEIGHT

                crop = source.crop((box.x1, box.y1, box.x2, box.y2))
                crop = ImageOps.contain(crop, (CELL_WIDTH - 16, CELL_HEIGHT - LABEL_HEIGHT - 16))
                crop_x = x + (CELL_WIDTH - crop.width) // 2
                crop_y = y + LABEL_HEIGHT + (CELL_HEIGHT - LABEL_HEIGHT - crop.height) // 2
                canvas.paste(crop, (crop_x, crop_y))

                draw.rectangle((x, y, x + CELL_WIDTH, y + LABEL_HEIGHT), fill='#1c1a17')
                draw.text((x + 10, y + 9), str(index), fill='white')
                indices.append(index)

            buffer = BytesIO()
            canvas.save(buffer, format='JPEG', quality=JPEG_QUALITY, optimize=True)
            sheets.append(ContactSheet(indices=tuple(indices), image_bytes=buffer.getvalue()))

    return tuple(sheets)
