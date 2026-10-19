import pptx
from pptx import Presentation
import xml.etree.ElementTree as ET

prs = Presentation('s:/SY/SEM 3/MP/EduVerse_AI_Review_2_Presentation.pptx')
slide_w = prs.slide_width
slide_h = prs.slide_height

print(f"Presentation dimensions: {slide_w / 914400:.2f} x {slide_h / 914400:.2f} inches ({slide_w} x {slide_h} EMU)")

# Let's inspect slide XML to see how images are used
for i, slide in enumerate(prs.slides):
    slide_xml = slide._element.xml
    root = ET.fromstring(slide_xml)
    print(f"\n=== SLIDE {i+1} ===")
    # find blip fills
    blips = root.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
    rel_ids = [b.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed') for b in blips]
    print(f"  Blip embed IDs: {rel_ids}")
    for rel_id in rel_ids:
        if rel_id and rel_id in slide.part.rels:
            rel = slide.part.rels[rel_id]
            print(f"    {rel_id} -> {rel.target_ref}")
