import pptx
from pptx import Presentation

prs = Presentation('s:/SY/SEM 3/MP/EduVerse_AI_Review_2_Presentation.pptx')

for i, slide in enumerate(prs.slides):
    print(f"\n==================== SLIDE {i+1} ====================")
    for s in slide.shapes:
        txt = s.text.strip().replace('\n', ' // ') if s.has_text_frame else ''
        pos = f"x={s.left/914400:.2f}\", y={s.top/914400:.2f}\", w={s.width/914400:.2f}\", h={s.height/914400:.2f}\""
        if txt:
            print(f"Shape '{s.name}' ({s.shape_type}) [{pos}]: {txt[:100]}")
        else:
            # check if it has blip or fill
            xml = s._element.xml
            blip_info = ""
            if "blip" in xml:
                import re
                m = re.findall(r'embed="([^"]+)"', xml)
                blip_info = f" [Blip: {m}]"
            print(f"Shape '{s.name}' ({s.shape_type}) [{pos}]{blip_info}")
