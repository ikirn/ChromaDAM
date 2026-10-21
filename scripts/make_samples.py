"""Create original, synthetic demo product illustrations; no network or AI needed."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'samples'
DEST.mkdir(exist_ok=True)


def canvas():
    image = Image.new('RGBA', (800, 600), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image)


def finish(image, name, bg):
    image.save(DEST / f'{name}.png')
    if name == 'crimson-running-shoe':
        base = Image.new('RGB', image.size, bg)
        base.paste(image, mask=image.getchannel('A'))
        base.save(DEST / f'{name}-opaque.jpg', quality=95)


image, d = canvas()
d.polygon([(145,365),(185,290),(215,208),(290,244),(330,322),(555,365),(648,387),(655,421),(161,421)], fill='#CE3F4A')
d.polygon([(215,208),(260,224),(280,285),(330,322),(302,345),(256,296)], fill='#A82F3E')
d.rounded_rectangle((142,404,659,447),radius=16,fill='#F3E7D5')
d.line([(167,432),(625,432)],fill='#CCC3B8',width=5)
d.polygon([(340,342),(507,365),(492,385),(328,363)],fill='#F5D8B9')
for i in range(5):
    x,y = 277+i*24,294+i*10
    d.line([(x,y),(x+34,y-12)],fill='#F8E9D3',width=8)
d.line([(191,365),(217,300)],fill='#E97A7C',width=7)
finish(image,'crimson-running-shoe','#F4DFDA')

image, d = canvas()
d.rounded_rectangle((275,230,525,485),radius=27,fill='#5B8766',outline='#456C50',width=4)
d.rounded_rectangle((297,247,323,450),radius=12,fill='#789E7F')
d.rounded_rectangle((340,148,460,238),radius=8,fill='#C3AD79')
for x in range(348,460,11): d.line((x,153,x,231),fill='#A89362',width=2)
d.rectangle((319,315,485,410),fill='#EEE9D9')
d.text((356,345),'BOTANIC',fill='#405A49',font=ImageFont.load_default(size=22))
d.text((358,376),'EAU DE PARFUM',fill='#6F7C68',font=ImageFont.load_default(size=12))
finish(image,'botanic-perfume','#E7EEE4')

image,d=canvas()
d.arc((244,138,557,453),180,360,fill='#6F5F9B',width=44)
d.arc((260,154,541,437),180,360,fill='#B4A3D1',width=16)
d.rounded_rectangle((227,302,315,451),radius=30,fill='#67558B')
d.rounded_rectangle((485,302,573,451),radius=30,fill='#67558B')
d.rounded_rectangle((244,312,296,440),radius=23,fill='#A99AC4')
d.rounded_rectangle((503,312,555,440),radius=23,fill='#A99AC4')
finish(image,'lilac-headphones','#EDE7F5')

image,d=canvas()
d.rounded_rectangle((180,223,620,452),radius=27,fill='#3E474C')
d.rectangle((211,236,590,300),fill='#B8B5A5')
d.rounded_rectangle((230,182,325,236),radius=8,fill='#4F595F')
d.rounded_rectangle((493,200,570,223),radius=5,fill='#6C7271')
d.ellipse((298,249,508,459),fill='#252E34',outline='#757D7B',width=11)
d.ellipse((323,274,483,434),fill='#536673',outline='#A6A69A',width=8)
d.ellipse((347,298,459,410),fill='#263E50')
d.ellipse((363,310,396,343),fill='#A1BDCA')
d.ellipse((218,319,239,340),fill='#BD784E')
finish(image,'studio-film-camera','#E5E9E8')

image,d=canvas()
d.arc((300,110,500,350),180,360,fill='#BD713F',width=25)
d.polygon([(257,241),(543,241),(586,486),(213,486)],fill='#D59157')
d.polygon([(257,241),(283,241),(255,486),(213,486)],fill='#B97648')
d.line([(285,264),(270,456),(544,456),(518,264)],fill='#E4AE7F',width=4)
d.ellipse((345,322,456,425),fill='#F5D8AE')
d.line((372,385,394,406,432,351),fill='#A5633A',width=9)
finish(image,'sunset-canvas-tote','#F4E8D9')

image,d=canvas()
d.line((402,385,391,174),fill='#4E795C',width=10)
for box in [(288,190,395,300),(391,152,498,262),(300,275,407,355),(397,245,512,335)]:
    d.ellipse(box,fill='#608D6C')
d.polygon([(319,365),(485,365),(464,493),(343,493)],fill='#C4785E')
d.rounded_rectangle((310,350,495,380),radius=8,fill='#DB9379')
finish(image,'terracotta-desk-plant','#ECE8DE')
print(f'Created 7 synthetic demo images in {DEST}')
