from PIL import Image

img = Image.open(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\brave_maximized.png")
# Crop left sidebar: x: 0..400, y: 50..350
crop_left = img.crop((0, 50, 400, 350))
crop_left.save(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\crop_max_left.png")

# Crop right patch: x: 1650..1900, y: 380..500
crop_right = img.crop((1650, 380, 1900, 500))
crop_right.save(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\crop_max_right.png")

print("Saved crop_max_left.png and crop_max_right.png")
