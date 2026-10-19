import os
from PIL import Image

assets_dir = 's:/SY/SEM 3/MP/extracted_assets'
for f in ['image8.png', 'image11.png', 'image27.png', 'image28.png', 'image10.jpeg', 'image7.jpeg', 'image9.jpeg']:
    p = os.path.join(assets_dir, f)
    if os.path.exists(p):
        im = Image.open(p)
        print(f"{f}: size={im.size}, mode={im.mode}")
