from PIL import Image
import numpy as np

img = Image.open(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\brave_overleaf_screen.png")
# Let's crop x: 0 to 300, y: 50 to 250 (typical sidebar area)
crop1 = img.crop((0, 70, 300, 250))
crop1.save(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\crop_sidebar.png")

# Let's find green pixels in this crop
arr = np.array(crop1)
# Overleaf green button: R: ~20-50, G: ~120-180, B: ~40-90
mask = (arr[:, :, 1] > 120) & (arr[:, :, 0] < 80) & (arr[:, :, 2] < 100)
coords = np.argwhere(mask)
if len(coords) > 0:
    y_min, x_min = coords.min(axis=0)[:2]
    y_max, x_max = coords.max(axis=0)[:2]
    # Add offset
    real_x = (x_min + x_max) // 2
    real_y = 70 + (y_min + y_max) // 2
    print(f"Exact Green Button in Brave: ({real_x}, {real_y})")
else:
    print("Green button not in 0..300, 70..250. Checking entire image for green clusters...")
    full_arr = np.array(img)
    full_mask = (full_arr[:, :, 1] > 120) & (full_arr[:, :, 0] < 80) & (full_arr[:, :, 2] < 100)
    # Find connected components or bounding boxes of green patches
    from scipy.ndimage import label
    try:
        labeled, num_features = label(full_mask)
        print(f"Found {num_features} green patches.")
        for i in range(1, num_features + 1):
            patch_coords = np.argwhere(labeled == i)
            if len(patch_coords) > 500: # larger than 500 pixels (button size)
                p_ymin, p_xmin = patch_coords.min(axis=0)[:2]
                p_ymax, p_xmax = patch_coords.max(axis=0)[:2]
                cx = (p_xmin + p_xmax) // 2
                cy = (p_ymin + p_ymax) // 2
                print(f"  Patch {i}: center=({cx}, {cy}), size={len(patch_coords)} px, bbox=({p_xmin}, {p_ymin}, {p_xmax}, {p_ymax})")
    except Exception as e:
        print("Scipy error:", e)
