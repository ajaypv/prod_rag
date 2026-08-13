"""Generate the small, locally hosted newspaper animations used by glossary chapters."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT = 640, 360
FRAMES = 24
PAPER = (247, 243, 233)
INK = (42, 40, 35)
MUTED = (116, 107, 93)
LINE = (194, 184, 166)
WASH = (226, 217, 201)
ACCENT = (137, 111, 74)

OUTPUT = Path(__file__).resolve().parents[1] / "public" / "media" / "glossary"
FONT_DIR = Path("C:/Windows/Fonts")


def font(size: int, bold: bool = False):
    candidates = [
        FONT_DIR / ("georgiab.ttf" if bold else "georgia.ttf"),
        FONT_DIR / ("arialbd.ttf" if bold else "arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


LABEL = font(15, bold=True)
SMALL = font(12)


def ease(value: float) -> float:
    return value * value * (3 - 2 * value)


def base_frame(title: str, issue: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(image)
    draw.rectangle((9, 9, WIDTH - 10, HEIGHT - 10), outline=LINE, width=1)
    draw.line((28, 49, WIDTH - 28, 49), fill=INK, width=2)
    draw.line((28, 53, WIDTH - 28, 53), fill=LINE, width=1)
    draw.text((30, 23), title.upper(), font=LABEL, fill=INK)
    issue_width = draw.textbbox((0, 0), issue.upper(), font=SMALL)[2]
    draw.text((WIDTH - 30 - issue_width, 25), issue.upper(), font=SMALL, fill=MUTED)
    for y in range(72, HEIGHT - 20, 22):
        for x in range(24 + (y // 22 % 2) * 9, WIDTH - 20, 26):
            draw.ellipse((x, y, x + 1, y + 1), fill=(224, 217, 204))
    return image, draw


def card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], heading: str, lines: int = 3, active: bool = False):
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=5, fill=(240, 235, 224), outline=ACCENT if active else MUTED, width=3 if active else 1)
    draw.text((x1 + 13, y1 + 11), heading, font=SMALL, fill=INK)
    for index in range(lines):
        length = (x2 - x1 - 28) * (0.9 - index * 0.11)
        y = y1 + 38 + index * 13
        draw.line((x1 + 14, y, x1 + 14 + length, y), fill=MUTED, width=2)


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], progress: float = 1):
    x1, y1 = start
    x2, y2 = end
    px = x1 + (x2 - x1) * progress
    py = y1 + (y2 - y1) * progress
    draw.line((x1, y1, px, py), fill=ACCENT, width=3)
    if progress > 0.92:
        angle = math.atan2(y2 - y1, x2 - x1)
        for offset in (2.55, -2.55):
            draw.line((x2, y2, x2 + 10 * math.cos(angle + offset), y2 + 10 * math.sin(angle + offset)), fill=ACCENT, width=3)


def save(frames: list[Image.Image], name: str):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    palette = frames[0].quantize(colors=32, method=Image.Quantize.MEDIANCUT)
    indexed = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    indexed[0].save(
        OUTPUT / name,
        save_all=True,
        append_images=indexed[1:],
        duration=90,
        loop=0,
        disposal=2,
        optimize=True,
    )


def foundations():
    frames = []
    for frame_index in range(FRAMES):
        t = frame_index / (FRAMES - 1)
        image, draw = base_frame("The evidence route", "Foundations")
        card(draw, (34, 128, 166, 218), "QUESTION", 2)
        card(draw, (254, 92, 386, 182), "SOURCES", 3, active=0.28 < t < 0.72)
        card(draw, (474, 128, 606, 218), "ANSWER", 3, active=t > 0.7)
        arrow(draw, (166, 173), (254, 137), ease(min(1, t * 2.2)))
        arrow(draw, (386, 137), (474, 173), ease(max(0, min(1, (t - 0.45) * 2.2))))
        dot_x = 166 + (308 * ease(t))
        dot_y = 173 - 36 * math.sin(math.pi * t)
        draw.ellipse((dot_x - 6, dot_y - 6, dot_x + 6, dot_y + 6), fill=ACCENT)
        draw.text((199, 270), "FIND  •  SELECT  •  ANSWER", font=LABEL, fill=INK)
        frames.append(image)
    save(frames, "foundations.gif")


def ingestion():
    frames = []
    chunk_boxes = [(305, 91, 485, 137), (305, 151, 485, 197), (305, 211, 485, 257)]
    for frame_index in range(FRAMES):
        t = ease(frame_index / (FRAMES - 1))
        image, draw = base_frame("From document to passages", "Ingestion")
        doc_x = int(52 - 13 * t)
        card(draw, (doc_x, 85, doc_x + 166, 274), "SOURCE PDF", 10)
        split_progress = max(0, min(1, (t - 0.12) * 1.7))
        arrow(draw, (doc_x + 166, 180), (281, 180), split_progress)
        for index, box in enumerate(chunk_boxes):
            local = max(0, min(1, (t - 0.25 - index * 0.08) * 2.2))
            shifted = tuple(int(value + (1 - local) * 80) if i % 2 == 0 else value for i, value in enumerate(box))
            card(draw, shifted, f"CHUNK {index + 1}", 1, active=index == int(t * 3) % 3)
        if t > 0.6:
            draw.rounded_rectangle((518, 120, 602, 231), radius=5, outline=ACCENT, width=2)
            draw.text((537, 139), "INDEX", font=SMALL, fill=INK)
            for y in (174, 194, 214):
                draw.ellipse((544, y, 554, y + 10), outline=MUTED)
                draw.line((560, y + 5, 582, y + 5), fill=MUTED, width=2)
            arrow(draw, (485, 180), (518, 180), max(0, (t - 0.6) * 2.5))
        draw.text((52, 306), "Structure first. Chunk second. Keep the source.", font=LABEL, fill=INK)
        frames.append(image)
    save(frames, "ingestion.gif")


def retrieval():
    frames = []
    for frame_index in range(FRAMES):
        t = frame_index / (FRAMES - 1)
        image, draw = base_frame("Two searches, one shortlist", "Retrieval")
        card(draw, (35, 132, 157, 212), "QUERY", 2)
        card(draw, (255, 82, 393, 157), "MEANING", 2, active=0.2 < t < 0.55)
        card(draw, (255, 215, 393, 290), "KEYWORDS", 2, active=0.45 < t < 0.8)
        card(draw, (497, 132, 605, 212), "FUSED", 2, active=t > 0.72)
        phase_a = ease(min(1, t * 2.4))
        phase_b = ease(max(0, min(1, (t - 0.35) * 2.4)))
        arrow(draw, (157, 172), (255, 120), phase_a)
        arrow(draw, (157, 172), (255, 252), phase_a)
        arrow(draw, (393, 120), (497, 172), phase_b)
        arrow(draw, (393, 252), (497, 172), phase_b)
        for radius in range(16, 58, 14):
            alpha_phase = (t * 2 + radius / 60) % 1
            color = ACCENT if alpha_phase < 0.55 else LINE
            draw.arc((96 - radius, 172 - radius, 96 + radius, 172 + radius), 205, 335, fill=color, width=2)
        draw.text((192, 316), "SEMANTIC + EXACT MATCH", font=LABEL, fill=INK)
        frames.append(image)
    save(frames, "retrieval.gif")


def ranking():
    frames = []
    start_y = [96, 142, 188, 234]
    final_y = [188, 96, 234, 142]
    for frame_index in range(FRAMES):
        t = ease(frame_index / (FRAMES - 1))
        image, draw = base_frame("The shortlist changes order", "Ranking")
        draw.text((51, 78), "RETRIEVED", font=SMALL, fill=MUTED)
        draw.text((452, 78), "RERANKED", font=SMALL, fill=MUTED)
        for index in range(4):
            y = int(start_y[index] + (final_y[index] - start_y[index]) * t)
            x = int(55 + 392 * t)
            box = (x, y, x + 132, y + 34)
            draw.rounded_rectangle(box, radius=4, fill=WASH, outline=ACCENT if final_y[index] <= 142 and t > 0.75 else MUTED, width=2)
            draw.text((x + 10, y + 9), f"PASSAGE {chr(65 + index)}", font=SMALL, fill=INK)
        if t < 0.5:
            arrow(draw, (213, 183), (392, 183), t * 2)
        else:
            draw.text((248, 171), "READ AGAINST", font=SMALL, fill=MUTED)
            draw.text((273, 190), "QUERY", font=LABEL, fill=INK)
        draw.text((170, 314), "BROAD RECALL  TO  FINAL PRECISION", font=LABEL, fill=INK)
        frames.append(image)
    save(frames, "ranking.gif")


def evaluation():
    frames = []
    for frame_index in range(FRAMES):
        t = ease(frame_index / (FRAMES - 1))
        image, draw = base_frame("Measure each part", "Evaluation")
        gauges = [(145, "RECALL", 0.92), (320, "PRECISION", 0.78), (495, "FAITHFUL", 0.88)]
        for center_x, label, target in gauges:
            box = (center_x - 54, 105, center_x + 54, 213)
            draw.arc(box, 155, 385, fill=LINE, width=12)
            draw.arc(box, 155, 155 + int(230 * target * t), fill=ACCENT, width=12)
            value = int(target * t * 100)
            value_text = f"{value}%"
            text_width = draw.textbbox((0, 0), value_text, font=LABEL)[2]
            draw.text((center_x - text_width / 2, 155), value_text, font=LABEL, fill=INK)
            label_width = draw.textbbox((0, 0), label, font=SMALL)[2]
            draw.text((center_x - label_width / 2, 230), label, font=SMALL, fill=MUTED)
        if t > 0.72:
            draw.rounded_rectangle((207, 276, 433, 321), radius=4, outline=INK, width=2)
            draw.line((227, 299, 237, 309), fill=ACCENT, width=4)
            draw.line((237, 309, 253, 288), fill=ACCENT, width=4)
            draw.text((270, 291), "RELEASE CHECK", font=LABEL, fill=INK)
        frames.append(image)
    save(frames, "evaluation.gif")


if __name__ == "__main__":
    foundations()
    ingestion()
    retrieval()
    ranking()
    evaluation()
    for path in sorted(OUTPUT.glob("*.gif")):
        print(f"{path.name}: {path.stat().st_size:,} bytes")
