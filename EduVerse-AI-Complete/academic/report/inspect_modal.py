from PIL import Image

img = Image.open(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\modal_screen.png")
w, h = img.size
# Crop center modal area
crop = img.crop((w//4, h//4, 3*w//4, 3*h//4))
crop.save(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\crop_modal.png")
print(f"Saved crop_modal.png, size: {crop.size}")
