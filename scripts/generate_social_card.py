"""Generate the Open Graph preview image for the public project website."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "public" / "assets" / "social-card.png"
WIDTH = 1200
HEIGHT = 630


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size=size)


def generate() -> None:
    """Write the deterministic 1200 × 630 social preview PNG."""
    image = Image.new("RGB", (WIDTH, HEIGHT), "#07110f")
    draw = ImageDraw.Draw(image, "RGBA")

    for radius, alpha in ((430, 22), (330, 28), (230, 34)):
        draw.ellipse(
            (820 - radius, -130 - radius, 820 + radius, -130 + radius),
            fill=(153, 223, 36, alpha),
        )
    for x in range(38, WIDTH, 48):
        for y in range(38, HEIGHT, 48):
            draw.ellipse((x, y, x + 2, y + 2), fill=(209, 233, 218, 22))

    draw.rounded_rectangle((64, 57, 126, 119), radius=17, fill="#16261d", outline="#9cdf2b", width=2)
    draw.arc((79, 70, 110, 101), 180, 305, fill="#9cdf2b", width=4)
    draw.polygon(((105, 67), (114, 79), (100, 80)), fill="#9cdf2b")
    draw.arc((80, 75, 111, 106), 0, 125, fill="#9cdf2b", width=4)
    draw.polygon(((84, 109), (75, 97), (89, 96)), fill="#9cdf2b")

    draw.text((146, 67), "IDM", font=_font(31, bold=True), fill="#f2f7f3")
    draw.text((216, 67), "HEATPUMP", font=_font(31, bold=True), fill="#9cdf2b")
    draw.text((65, 169), "IDM heat pumps", font=_font(67, bold=True), fill="#f4f8f5")
    draw.text((65, 247), "in Home Assistant.", font=_font(67, bold=True), fill="#9cdf2b")
    draw.text((68, 349), "Local control and monitoring via Modbus TCP.", font=_font(29), fill="#b9c9bf")
    draw.text((68, 391), "Open source, HACS-ready and cloud-free.", font=_font(29), fill="#b9c9bf")

    badges = ("NAVIGATOR 2.0 / 10 / PRO", "MODBUS TCP", "NO CLOUD")
    x = 68
    badge_font = _font(17, bold=True)
    for badge in badges:
        box = draw.textbbox((0, 0), badge, font=badge_font)
        width = box[2] - box[0] + 34
        draw.rounded_rectangle((x, 487, x + width, 533), radius=23, fill="#132219", outline="#355140", width=1)
        draw.text((x + 17, 498), badge, font=badge_font, fill="#dce8e0")
        x += width + 13

    draw.rounded_rectangle((887, 164, 1135, 474), radius=30, fill="#0d1a15", outline="#294437", width=2)
    draw.rounded_rectangle((918, 194, 1104, 237), radius=21, fill="#18291f")
    draw.ellipse((934, 207, 946, 219), fill="#9cdf2b")
    draw.text((958, 204), "CONNECTED", font=_font(16, bold=True), fill="#dce8e0")
    draw.text((918, 278), "31.4°", font=_font(57, bold=True), fill="#f4f8f5")
    draw.text((921, 345), "FLOW TEMPERATURE", font=_font(15, bold=True), fill="#81978a")
    draw.line((921, 392, 1096, 392), fill="#294437", width=2)
    draw.text((921, 414), "100% LOCAL", font=_font(18, bold=True), fill="#9cdf2b")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT, format="PNG", optimize=True)


if __name__ == "__main__":
    generate()
