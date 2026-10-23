from PIL import Image
import numpy as np

img = Image.open(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\brave_overleaf_screen.png")
arr = np.array(img)
print("Image shape:", arr.shape)

# Overleaf "New Project" button is distinct green: high green, lower red and blue
# e.g. R in [10, 80], G in [120, 200], B in [20, 100]
mask = (arr[:, :, 0] < 80) & (arr[:, :, 1] > 120) & (arr[:, :, 2] < 100)
coords = np.argwhere(mask)
if len(coords) > 0:
    y_min, x_min = coords.min(axis=0)[:2]
    y_max, x_max = coords.max(axis=0)[:2]
    print(f"Found green region: x=({x_min}, {x_max}), y=({y_min}, {y_max}), center=({(x_min+x_max)//2}, {(y_min+y_max)//2})")
else:
    print("No green button found, checking for button-like elements...")
