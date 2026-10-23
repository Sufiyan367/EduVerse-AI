from PIL import Image

img = Image.open(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\modal_screen.png")
# Crop around the upload box: x: 300 to 700, y: 220 to 420
crop = img.crop((300, 220, 700, 420))
crop.save(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\box_crop.png")
print("Saved box_crop.png, size:", crop.size)
