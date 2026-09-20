"""Software-only effect preview; requires Pillow on the Mac, never on the Pico."""
import argparse
import math
from pathlib import Path
import random
import sys
import tempfile
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'board'))
from engine import Engine
from presets import Store
from effects import NAMES

def audio(e,t):
 hit=math.exp(-((t*1.2)%1)*8)
 e.audio.push([.25+.7*hit,.45+.25*math.sin(t),.3,.5+.3*hit,hit,0,.2])

def main():
 parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args()
 out=Path(args.output);out.mkdir(parents=True,exist_ok=True);random.seed(42)
 with tempfile.TemporaryDirectory() as tmp:
  e=Engine(Store(tmp+'/settings.json'))
  image=Image.new('RGB',(1200,810),(10,10,18));draw=ImageDraw.Draw(image)
  try:
   title=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',28)
   label=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',17)
  except OSError: title=label=ImageFont.load_default()
  draw.text((30,22),'GALACTIC WLED  /  EFFECT LIBRARY',font=title,fill=(235,225,255))
  draw.text((30,64),'Actual engine output • synthetic audio • software preview, not measured LED brightness',font=label,fill=(160,150,180))
  palette={'fire':'fire','digital_rain':'matrix','rain':'ice','sunrise':'sunrise','spectrum':'audio_spectrum','spectral_history':'cyberpunk','cassette':'warm_sunset','starfield':'ice','center_pulse':'neon'}
  for index,name in enumerate(NAMES):
   e.apply({'effect':name,'palette':palette.get(name,'purple_haze'),'layers':[]},0)
   for i in range(120): audio(e,i*.04);e.step(.04)
   if name=='sunrise': e.contexts[0].phase=45;e.step(.04)
   frame=Image.frombytes('RGB',(53,11),bytes(e.display)).resize((371,77),Image.Resampling.NEAREST)
   x=30+(index%3)*395;y=113+(index//3)*136
   draw.text((x,y),name.replace('_',' ').title(),font=label,fill=(211,194,235))
   image.paste(frame,(x,y+29))
  image.save(out/'effects-preview.png')
  e.apply_preset('Moody R&B',0);frames=[]
  for i in range(100):
   audio(e,i*.05);e.step(.05)
   raw=Image.frombytes('RGB',(53,11),bytes(e.display)).resize((636,132),Image.Resampling.NEAREST)
   frame=Image.new('RGB',(684,214),(10,10,18));d=ImageDraw.Draw(frame)
   d.text((24,15),'Moody R&B  /  Plasma + subtle particles',font=label,fill=(220,205,240));frame.paste(raw,(24,58));frames.append(frame)
  frames[0].save(out/'showcase-preview.gif',save_all=True,append_images=frames[1:],duration=50,loop=0)
if __name__=='__main__': main()
