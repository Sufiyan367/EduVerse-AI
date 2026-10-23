from PIL import Image
import numpy as np
from scipy.ndimage import label

img = Image.open(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\brave_maximized.png")
arr = np.array(img)

mask = (arr[:, :, 1] > 120) & (arr[:, :, 0] < 70) & (arr[:, :, 2] < 90)
labeled, num_features = label(mask)
print("Num green features:", num_features)

for i in range(1, num_features + 1):
    c = np.argwhere(labeled == i)
    if len(c) > 500: # button sized
        ymin, xmin = c.min(axis=0)[:2]
        ymax, xmax = c.max(axis=0)[:2]
        cx = (xmin + xmax) // 2
        cy = (ymin + ymax) // 2
        print(f"Button patch {i}: center=({cx}, {cy}), bbox=({xmin}, {ymin}) to ({xmax}, {ymax}), count={len(c)}")
