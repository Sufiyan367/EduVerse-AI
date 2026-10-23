from PIL import Image
import numpy as np

img = Image.open(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\modal_screen.png")
arr = np.array(img)
w, h = img.size

# Let's inspect where the white modal card is located
# Usually modal background is semi-transparent dark grey, and modal content is white
# Let's find white pixels: R > 240, G > 240, B > 240
white_mask = (arr[:, :, 0] > 240) & (arr[:, :, 1] > 240) & (arr[:, :, 2] > 240)
# Find rows and cols in center where white is prevalent
row_counts = white_mask.sum(axis=1)
col_counts = white_mask.sum(axis=0)

y_indices = np.where(row_counts > 300)[0]
x_indices = np.where(col_counts > 200)[0]

if len(y_indices) > 0 and len(x_indices) > 0:
    modal_ymin, modal_ymax = y_indices[0], y_indices[-1]
    modal_xmin, modal_xmax = x_indices[0], x_indices[-1]
    print(f"Modal bounds: x=({modal_xmin}, {modal_xmax}), y=({modal_ymin}, {modal_ymax})")
    
    # Inside this modal, let's find the button (colored or bordered)
    modal_arr = arr[modal_ymin:modal_ymax, modal_xmin:modal_xmax]
    # Check for non-white/non-gray elements (buttons)
    # E.g. colored pixels where max(RGB) - min(RGB) > 30
    color_diff = modal_arr.max(axis=2) - modal_arr.min(axis=2)
    colored_mask = color_diff > 40
    c_coords = np.argwhere(colored_mask)
    if len(c_coords) > 0:
        c_ymin, c_xmin = c_coords.min(axis=0)
        c_ymax, c_xmax = c_coords.max(axis=0)
        real_cx = modal_xmin + (c_xmin + c_xmax) // 2
        real_cy = modal_ymin + (c_ymin + c_ymax) // 2
        print(f"Colored button inside modal: ({real_cx}, {real_cy}), bbox=({modal_xmin+c_xmin}, {modal_ymin+c_ymin}) to ({modal_xmin+c_xmax}, {modal_ymin+c_ymax})")
else:
    print("Could not find white modal box.")
