"""產生程式圖示 assets/icon.png 與 packaging/icon.ico（藍底白色貨箱＋「進銷存」）。"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(HERE, "assets", "fonts", "NotoSansTC-VF.ttf")


def draw(size=1024):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 1024
    d.rounded_rectangle([40 * s, 40 * s, 984 * s, 984 * s], radius=200 * s, fill=(31, 95, 168, 255))
    # 貨箱
    d.rounded_rectangle([250 * s, 170 * s, 774 * s, 300 * s], radius=30 * s, fill="white")
    d.rounded_rectangle([290 * s, 320 * s, 734 * s, 640 * s], radius=30 * s, fill="white")
    d.rounded_rectangle([430 * s, 400 * s, 594 * s, 450 * s], radius=20 * s, fill=(31, 95, 168, 255))
    try:
        f = ImageFont.truetype(FONT, int(230 * s))
        f.set_variation_by_axes([800])
    except Exception:
        f = ImageFont.truetype(FONT, int(230 * s))
    d.text((512 * s, 810 * s), "進銷存", font=f, fill="white", anchor="mm")
    return img


if __name__ == "__main__":
    img = draw()
    img.save(os.path.join(HERE, "assets", "icon.png"))
    os.makedirs(os.path.join(HERE, "packaging"), exist_ok=True)
    img.save(os.path.join(HERE, "packaging", "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                                              (128, 128), (256, 256)])
    print("ok")
