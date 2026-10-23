from PIL import Image
import numpy as np

img = Image.open(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\brave_maximized.png")
arr = np.array(img)

# Look for Overleaf green button:
# R: 10..70, G: 120..180, B: 30..90
mask = (arr[:, :, 1] > 120) & (arr[:, :, 0] < 70) & (arr[:, :, 2] < 90)
coords = np.argwhere(mask)
if len(coords) > 0:
    ymin, xmin = coords.min(axis=0)[:2]
    ymax, xmax = coords.max(axis=0)[:2]
    cx = (xmin + xmax) // 2
    cy = (ymin + ymax) // 2
    print(f"Green New Project button found: center=({cx}, {cy}), bbox=({xmin}, {ymin}) to ({xmax}, {ymax}), pixel count={len(coords)}")
else:
    print("Could not find green button. Searching entire image for any green...")
    mask2 = (arr[:, :, 1] > 100) & (arr[:, :, 1] > arr[:, :, 0] + 40) & (arr[:, :, 1] > arr[:, :, 2] + 40)
    coords2 = np.argwhere(mask2)
    print("Green-ish pixels found:", len(coords2))
    if len(coords2) > 0:
        print("Bbox:", coords2.min(axis=0)[:2], "to", coords2.max(axis=0)[:2])
