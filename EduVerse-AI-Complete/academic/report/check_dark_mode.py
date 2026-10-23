from PIL import Image
import numpy as np

img = Image.open(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\modal_screen.png")
arr = np.array(img)
print("Image mean RGB:", arr.mean(axis=(0,1)))
print("Top-left pixel RGB:", arr[10, 10])
print("Center pixel RGB:", arr[500, 500])
