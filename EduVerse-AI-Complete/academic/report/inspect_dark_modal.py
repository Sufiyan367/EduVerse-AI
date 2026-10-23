from PIL import Image
import numpy as np

img = Image.open(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\modal_screen.png")
arr = np.array(img)
h, w, _ = arr.shape

# Let's inspect brightness across columns and rows to find the modal dialog
brightness = arr.mean(axis=2)
# Find the dialog box which is typically brighter or distinct from the darkened overlay
# Let's look for contrast edges
print("Min brightness:", brightness.min(), "Max brightness:", brightness.max(), "Median:", np.median(brightness))

# Find pixels with high contrast or distinct colors
# Overleaf's "Select a .zip file" button in dark mode is often bright blue or green
# Let's find any pixels with saturated color:
max_c = arr.max(axis=2)
min_c = arr.min(axis=2)
saturation = max_c - min_c
sat_coords = np.argwhere(saturation > 60)
print(f"Total saturated pixels: {len(sat_coords)}")

if len(sat_coords) > 0:
    # Cluster or inspect regions
    print("Saturated regions:")
    # Group by y
    y_vals = sat_coords[:, 0]
    x_vals = sat_coords[:, 1]
    print(f"  y range: {y_vals.min()} to {y_vals.max()}")
    print(f"  x range: {x_vals.min()} to {x_vals.max()}")
    
    # Let's find centers of dense clusters
    from collections import Counter
    y_bins = Counter(y_vals // 20)
    for y_bin, count in y_bins.most_common(5):
        y_center = y_bin * 20 + 10
        matching_x = x_vals[(y_vals >= y_bin*20) & (y_vals < (y_bin+1)*20)]
        x_center = int(np.mean(matching_x))
        color_sample = arr[y_center, x_center]
        print(f"  Cluster at y~{y_center}, x~{x_center} ({count} pts), color={color_sample}")
