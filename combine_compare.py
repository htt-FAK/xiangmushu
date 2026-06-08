from PIL import Image, ImageDraw
import os

out_dir = os.path.join(os.getcwd(), "artifacts", "page_screenshots")
pages = ["login", "home", "generate", "knowledge", "settings", "template"]
labels = ["Login", "Home", "Generate", "Knowledge", "Settings", "Template"]

# Target: desktop on left, mobile on right, side by side
desktop_w = 900
mobile_w = 390
gap = 20
label_h = 45
section_gap = 40

rows = []
for name, label in zip(pages, labels):
    d_img = Image.open(os.path.join(out_dir, f"desktop_{name}.png"))
    m_img = Image.open(os.path.join(out_dir, f"mobile_{name}.png"))

    # Resize desktop
    d_ratio = desktop_w / d_img.width
    d_img = d_img.resize((desktop_w, int(d_img.height * d_ratio)), Image.LANCZOS)

    # Resize mobile
    m_ratio = mobile_w / m_img.width
    m_img = m_img.resize((mobile_w, int(m_img.height * m_ratio)), Image.LANCZOS)

    rows.append((label, d_img, m_img))

total_w = desktop_w + gap + mobile_w
total_h = sum(max(d.height, m.height) for _, d, m in rows) + label_h * len(rows) + section_gap * (len(rows) - 1)

canvas = Image.new("RGB", (total_w, total_h), (5, 6, 10))
draw = ImageDraw.Draw(canvas)

y = 0
for i, (label, d_img, m_img) in enumerate(rows):
    # Label
    draw.text((10, y + 8), f"{i+1}. {label}", fill=(54, 242, 230))
    draw.text((desktop_w + gap + 10, y + 8), "Mobile", fill=(130, 140, 160))
    y += label_h

    row_h = max(d_img.height, m_img.height)
    canvas.paste(d_img, (0, y))
    canvas.paste(m_img, (desktop_w + gap, y))
    y += row_h + section_gap

out_path = os.path.join(out_dir, "compare_all.jpg")
canvas.save(out_path, "JPEG", quality=82)
sz = os.path.getsize(out_path)
print(f"Saved: {total_w}x{total_h}, {sz//1024}KB -> {out_path}")
