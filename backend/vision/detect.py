"""Local CPU detection of book-shaped regions in a bookshelf photograph.

YOLO supplies the primary detections from its pretrained COCO ``book`` class.
COCO does not model bookshelf spines particularly well, so a lightweight
vertical-edge fallback remains available when YOLO finds too few boxes.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
from ultralytics import YOLO


YOLO_MODEL_NAME = 'yolov8n.pt'
YOLO_CONFIDENCE_THRESHOLD = 0.25
MIN_YOLO_BOXES = 2

# Fallback regions need to be tall enough to be plausible spines. The threshold
# is deliberately permissive: review is safer than silently losing a book.
MIN_FALLBACK_HEIGHT_RATIO = 0.08
MIN_FALLBACK_ASPECT_RATIO = 1.25
MAX_FALLBACK_WIDTH_RATIO = 0.35


@dataclass(frozen=True)
class BookBox:
    """A rectangular book candidate in image pixel coordinates."""

    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float | None

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1


@dataclass(frozen=True)
class DetectionResult:
    """Book candidates and the method that produced them."""

    route: str
    boxes: tuple[BookBox, ...]
    message: str


@lru_cache(maxsize=1)
def _model() -> YOLO:
    """Load the small pretrained detector once per Django process."""
    return YOLO(YOLO_MODEL_NAME)


def _clip_box(values, width: int, height: int, confidence: float | None) -> BookBox | None:
    x1, y1, x2, y2 = (int(round(value)) for value in values)
    x1, x2 = max(0, x1), min(width, x2)
    y1, y2 = max(0, y1), min(height, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return BookBox(x1=x1, y1=y1, x2=x2, y2=y2, confidence=confidence)


def _yolo_boxes(image) -> tuple[BookBox, ...]:
    """Keep only COCO detections whose named class is ``book``."""
    height, width = image.shape[:2]
    prediction = _model()(image, device='cpu', verbose=False)[0]
    boxes = []

    for detected in prediction.boxes:
        class_name = prediction.names[int(detected.cls.item())]
        confidence = float(detected.conf.item())
        if class_name != 'book' or confidence < YOLO_CONFIDENCE_THRESHOLD:
            continue

        box = _clip_box(detected.xyxy[0].tolist(), width, height, confidence)
        if box is not None:
            boxes.append(box)

    return tuple(sorted(boxes, key=lambda box: (box.x1, box.y1)))


def _fallback_boxes(image) -> tuple[BookBox, ...]:
    """Find tall vertical edge clusters when object detection is sparse.

    This is intentionally classical rather than learned: it is a degraded
    recovery path, not a competing spine detector. Its output is routed to the
    same downstream review mechanism and is never presented as high certainty.
    """
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)

    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(12, height // 12)))
    joined_edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, vertical_kernel)
    contours, _ = cv2.findContours(joined_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        if box_height < height * MIN_FALLBACK_HEIGHT_RATIO:
            continue
        if box_width <= 0 or box_width > width * MAX_FALLBACK_WIDTH_RATIO:
            continue
        if box_height / box_width < MIN_FALLBACK_ASPECT_RATIO:
            continue

        # An edge cluster marks one side of a spine, not necessarily both sides.
        # Expanding horizontally creates a legible crop for the later VLM step.
        padding = max(6, box_width // 2)
        box = _clip_box((x - padding, y, x + box_width + padding, y + box_height), width, height, None)
        if box is not None:
            candidates.append(box)

    return _deduplicate(candidates)


def _deduplicate(boxes: list[BookBox], overlap_threshold: float = 0.5) -> tuple[BookBox, ...]:
    """Collapse overlapping fallback contours into one candidate region."""
    kept = []
    for candidate in sorted(boxes, key=lambda box: box.height * box.width, reverse=True):
        overlaps = False
        for existing in kept:
            intersection = max(0, min(candidate.x2, existing.x2) - max(candidate.x1, existing.x1))
            union = max(candidate.width, existing.width)
            if union and intersection / union >= overlap_threshold:
                overlaps = True
                break
        if not overlaps:
            kept.append(candidate)

    return tuple(sorted(kept, key=lambda box: (box.x1, box.y1)))


def detect_books(image_path: str | Path) -> DetectionResult:
    """Detect books in one image, returning YOLO, fallback, or no detections."""
    image = cv2.imread(str(image_path))
    if image is None:
        return DetectionResult('none', (), 'The uploaded file could not be decoded as an image.')

    yolo = _yolo_boxes(image)
    if len(yolo) >= MIN_YOLO_BOXES:
        return DetectionResult('yolo', yolo, f'YOLO detected {len(yolo)} book candidates.')

    fallback = _fallback_boxes(image)
    if fallback:
        return DetectionResult(
            'opencv_fallback',
            fallback,
            f'YOLO found {len(yolo)} book candidates; vertical-edge fallback found {len(fallback)}.',
        )

    return DetectionResult(
        'none',
        (),
        f'YOLO found {len(yolo)} book candidates and the fallback found none.',
    )


def write_debug_image(image_path: str | Path, output_path: str | Path) -> DetectionResult:
    """Draw numbered boxes on a copy of an image for manual detector review."""
    result = detect_books(image_path)
    image = cv2.imread(str(image_path))
    if image is None:
        return result

    for index, box in enumerate(result.boxes, start=1):
        color = (56, 140, 35) if result.route == 'yolo' else (0, 140, 255)
        cv2.rectangle(image, (box.x1, box.y1), (box.x2, box.y2), color, 2)
        cv2.putText(image, str(index), (box.x1 + 4, box.y1 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), image)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description='Inspect local book-spine detection on one image.')
    parser.add_argument('image', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    result = write_debug_image(args.image, args.output)
    print(result.message)
    print(f'route={result.route} boxes={len(result.boxes)} output={args.output}')


if __name__ == '__main__':
    main()
