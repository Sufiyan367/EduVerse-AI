from PIL import Image

img = Image.open(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\dropdown_screen.png")
# Crop the dropdown menu area
crop = img.crop((50, 180, 250, 420))
crop.save(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\crop_dropdown.png")
print("Saved crop_dropdown.png")
