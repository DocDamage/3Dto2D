from pathlib import Path
from PIL import Image, ImageDraw
import math

out = Path(__file__).parent / "test_frames"
out.mkdir(parents=True, exist_ok=True)

for i in range(12):
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = 128 + int(math.sin(i / 12 * math.tau) * 18)
    y = 150 + int(math.sin(i / 12 * math.tau * 2) * 6)
    d.ellipse((x - 30, y - 80, x + 30, y - 20), fill=(70, 140, 255, 255))
    d.rectangle((x - 18, y - 20, x + 18, y + 40), fill=(40, 80, 180, 255))
    d.line((x - 8, y + 40, x - 20, 230), fill=(30, 30, 30, 255), width=8)
    d.line((x + 8, y + 40, x + 20, 230), fill=(30, 30, 30, 255), width=8)
    img.save(out / f"test_{i:04d}.png")

print(f"Wrote {out}")
