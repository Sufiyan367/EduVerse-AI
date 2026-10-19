import os
from PIL import Image

assets_dir = 's:/SY/SEM 3/MP/extracted_assets'
files = [f for f in os.listdir(assets_dir) if f.endswith(('.png', '.jpeg', '.jpg'))]
for f in sorted(files):
    p = os.path.join(assets_dir, f)
    im = Image.open(p)
    print(f"{f:15}: size={im.size}, mode={im.mode}")
