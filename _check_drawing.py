from docx import Document
import xml.etree.ElementTree as ET

doc = Document(r'data\templates\智能体应用开发实践.docx')

p2 = doc.paragraphs[2]
print(f"段落[2]: text={repr(p2.text)}")
print(f"runs数量: {len(p2.runs)}")

for i, r in enumerate(p2.runs):
    print(f"\n=== Run[{i}] ===")
    # 查找所有 drawing
    drawings = r._element.xpath(".//w:drawing")
    print(f"drawing数量: {len(drawings)}")

    for j, d in enumerate(drawings):
        # 检查是 inline 还是 anchor
        inlines = d.xpath(".//wp:inline")
        anchors = d.xpath(".//wp:anchor")
        print(f"  drawing[{j}]: inline={len(inlines)}, anchor={len(anchors)}")

        # 查找图片引用
        blips = d.xpath(".//a:blip")
        if blips:
            print(f"    含 {len(blips)} 个图片 (a:blip)")
            for b in blips:
                embed = b.get(
                    '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                print(f"      rId: {embed}")

        # 查找 WordArt
        shapes = d.xpath(".//wps:wsp")
        if shapes:
            print(f"    含 {len(shapes)} 个 WordArt (wps:wsp)")

        # 查找 VML shape
        vml_shapes = d.xpath(".//v:shape")
        if vml_shapes:
            print(f"    含 {len(vml_shapes)} 个 VML shape")
