from PIL import Image
import numpy as np

img = Image.open(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\upload_page_screen.png")
arr = np.array(img)
h, w, _ = arr.shape

# Let's find buttons (e.g. blue or green, or distinct from background)
# Background in dark mode is around RGB [30..50, 40..60, 50..80]
# Look for blue button (bootstrap primary button): R < 80, G in 100..180, B > 180
blue_mask = (arr[:, :, 2] > 180) & (arr[:, :, 0] < 80)
blue_coords = np.argwhere(blue_mask)
if len(blue_coords) > 0:
    ymin, xmin = blue_coords.min(axis=0)[:2]
    ymax, xmax = blue_coords.max(axis=0)[:2]
    cx = (xmin + xmax) // 2
    cy = (ymin + ymax) // 2
    print(f"Found Primary Blue Button at: ({cx}, {cy}), bbox=({xmin}, {ymin}) to ({xmax}, {ymax})")
else:
    # Check green button
    green_mask = (arr[:, :, 1] > 120) & (arr[:, :, 0] < 80) & (arr[:, :, 2] < 100)
    green_coords = np.argwhere(green_mask)
    if len(green_coords) > 0:
        ymin, xmin = green_coords.min(axis=0)[:2]
        ymax, xmax = green_coords.max(axis=0)[:2]
        cx = (xmin + xmax) // 2
        cy = (ymin + ymax) // 2
        print(f"Found Green Button at: ({cx}, {cy}), bbox=({xmin}, {ymin}) to ({xmax}, {ymax})")
    else:
        print("No primary colored button. Center pixel:", arr[h//2, w//2])
