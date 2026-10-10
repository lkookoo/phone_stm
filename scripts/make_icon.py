"""生成 X1.0 PWA 图标（192 和 512 真尺寸）"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

def make_icon(size, path):
    img = Image.new('RGB', (size, size), '#0d1117')
    draw = ImageDraw.Draw(img)

    # 缠论折线
    points = [
        (int(size*0.12), int(size*0.70)),
        (int(size*0.32), int(size*0.40)),
        (int(size*0.48), int(size*0.58)),
        (int(size*0.66), int(size*0.25)),
        (int(size*0.88), int(size*0.50)),
    ]
    for i in range(len(points) - 1):
        draw.line([points[i], points[i+1]], fill='#3fb950', width=int(size*0.05))

    # 分型点
    for p in points:
        r = int(size*0.035)
        draw.ellipse([p[0]-r, p[1]-r, p[0]+r, p[1]+r], fill='#f85149')

    # 文字 X1.0
    try:
        font = ImageFont.truetype("arial.ttf", int(size*0.22))
    except:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", int(size*0.22))
        except:
            font = ImageFont.load_default()

    text = "X1.0"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size-tw)//2, int(size*0.74)), text, fill='#e6edf3', font=font)

    img.save(path, 'PNG')
    print(f"saved: {path} ({size}x{size})")

if __name__ == '__main__':
    out = Path(__file__).resolve().parent.parent / 'frontend'
    # 覆盖你现有的错误尺寸图标
    make_icon(192, out / 'icon-192.png')
    make_icon(512, out / 'icon-512.png')
    print("done. 现在是真尺寸 192x192 和 512x512")