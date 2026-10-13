from PIL import Image
import os
OUT = r'G:\ArknightsCursorExtract\_diag\gameptr'
im = Image.open(os.path.join(OUT, 'user_game.png')).convert('RGB')
w, h = im.size
im.resize((w//2, h//2), Image.LANCZOS).save(os.path.join(OUT, 'ug_half.png'))
for tag, box in [('cand_a', (398-70, 396-70, 398+57+70, 396+66+70)),
                 ('cand_b', (934-70, 573-70, 934+57+70, 573+50+70)),
                 ('cand_c', (37-60, 1013-60, 37+55+60, 1013+79+60))]:
    sub = im.crop(box)
    sub.resize((sub.width*4, sub.height*4), Image.NEAREST).save(os.path.join(OUT, tag+'_4x.png'))
    print(tag, 'box=', box, 'size=', sub.size)
