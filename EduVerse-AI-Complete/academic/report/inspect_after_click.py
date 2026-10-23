from PIL import Image

img = Image.open(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\overleaf_editor_screen.png")
# Let's crop center to see if the modal is still there or if file dialog is open
crop = img.crop((150, 150, 800, 700))
crop.save(r"S:\SY\SEM 3\MP\EduVerse_AI_Project_Report\crop_after_click.png")
print("Saved crop_after_click.png")
