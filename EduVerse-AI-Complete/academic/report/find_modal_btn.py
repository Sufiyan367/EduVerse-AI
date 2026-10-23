from PIL import Image
import numpy as np

img = Image.open(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\modal_screen.png")
arr = np.array(img)
w, h = img.size

# Look for blue/green buttons or distinct boxes in the center
# Overleaf's "Select a .zip file" button is usually blue or green, or has a dashed border
# Let's inspect colors in the center box: x in [250, 750], y in [250, 700]
center = arr[250:700, 250:750]
print("Center slice shape:", center.shape)

# Let's check for blue button (typical bootstrap/overleaf primary button: R < 50, G in 100..180, B > 180 or similar)
blue_mask = (center[:, :, 2] > 180) & (center[:, :, 0] < 80)
blue_coords = np.argwhere(blue_mask)
if len(blue_coords) > 0:
    ymin, xmin = blue_coords.min(axis=0)[:2]
    ymax, xmax = blue_coords.max(axis=0)[:2]
    cx = 250 + (xmin + xmax) // 2
    cy = 250 + (ymin + ymax) // 2
    print(f"Found blue button at: ({cx}, {cy}), bbox: ({250+xmin}, {250+ymin}) to ({250+xmax}, {250+ymax})")
else:
    print("No blue button found. Checking for green button in modal...")
    green_mask = (center[:, :, 1] > 120) & (center[:, :, 0] < 80) & (center[:, :, 2] < 100)
    green_coords = np.argwhere(green_mask)
    if len(green_coords) > 0:
        ymin, xmin = green_coords.min(axis=0)[:2]
        ymax, xmax = green_coords.max(axis=0)[:2]
        cx = 250 + (xmin + xmax) // 2
        cy = 250 + (ymin + ymax) // 2
        print(f"Found green button at: ({cx}, {cy})")
    else:
        print("Checking center pixel colors...")
        # Print center of modal:
        cx = w // 2
        cy = h // 2
        print(f"Screen center is ({cx}, {cy}), pixel={arr[cy, cx]}")
