import zipfile, os, re
from PIL import Image

media_files = [f for f in os.listdir('s:/SY/SEM 3/MP/extracted_assets') if not f.endswith('.svg')]
for f in sorted(media_files, key=lambda x: (len(x), x)):
    path = os.path.join('s:/SY/SEM 3/MP/extracted_assets', f)
    try:
        im = Image.open(path)
        print(f'{f:15}: format={im.format:5}, size={str(im.size):12}, mode={im.mode}')
    except Exception as e:
        print(f'{f:15}: {e}')

print("\n--- Relationship mappings ---")
with zipfile.ZipFile('s:/SY/SEM 3/MP/EduVerse_AI_Review_2_Presentation.pptx', 'r') as z:
    for name in sorted(z.namelist()):
        if name.endswith('.rels'):
            content = z.read(name).decode('utf-8', errors='ignore')
            matches = re.findall(r'Target="([^"]*media[^"]*)"', content)
            if matches:
                print(f'{name:40} -> {matches}')
