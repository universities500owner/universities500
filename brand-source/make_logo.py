# Rebuilds public/brand/*.png and public/favicon.png from brand-source/logo-on-navy.jpg. Run from the repo root: python3 brand-source/make_logo.py
# Needs numpy, scipy and Pillow. The source is a JPEG on navy, so the script turns the navy into transparency,
# swaps the white parts for navy on the light version, and keeps the wordmark flat-coloured. A vector original would replace all of this.
import numpy as np
from PIL import Image
SRC='brand-source/logo-on-navy.jpg'
BG=np.array([1,9,56],float)
im=np.asarray(Image.open(SRC).convert('RGB'),float)

# colour-to-alpha against the navy background
def c2a(im):
    d=im-BG
    up=np.where(d>0,d/(255-BG),0); dn=np.zeros_like(up)   # nothing in the logo is darker than the navy: darker pixels are JPEG noise
    a=np.clip(np.max(np.maximum(up,dn),axis=2),0,1)
    a=np.where(a<0.06,0,a)                  # JPEG noise in the flat navy
    a=np.clip((a-0.035)/(1-0.035),0,1) if False else a
    safe=np.maximum(a,1e-6)[...,None]
    rgb=np.clip(BG+d/safe,0,255)
    return rgb,a
rgb,a=c2a(im)
from scipy import ndimage as ndi
core=a>0.15
lab,n=ndi.label(core)
sizes=ndi.sum(core,lab,range(1,n+1))
objs=ndi.find_objects(lab)
big=int(np.argmax(sizes))+1                    # the U mark with its 500 is the largest piece
ok=[]
for i,(sl,sz) in enumerate(zip(objs,sizes),start=1):
    y,x=sl
    if i==big: ok.append(i); continue
    in_text_row = x.start>=530 and y.start>=200 and y.stop<=335   # the wordmark; anything above, below or beside it is JPEG noise
    in_mark = x.stop<=526 and y.start>=100 and y.stop<=440 and sz>=1000   # pieces of the mark that the outline separates, such as the 5
    if (sz>=250 and in_text_row) or in_mark: ok.append(i)
keep=ndi.binary_dilation(np.isin(lab,ok),iterations=3)    # keep the soft edge around real shapes
a=np.where(keep,a,0)
ys,xs=np.where(a>0.08)
x0,x1,y0,y1=xs.min(),xs.max(),ys.min(),ys.max()
pad=6
x0,y0=max(0,x0-pad),max(0,y0-pad); x1,y1=min(im.shape[1]-1,x1+pad),min(im.shape[0]-1,y1+pad)
print('bbox',x0,y0,x1,y1,(x1-x0+1),(y1-y0+1))
rgb=rgb[y0:y1+1,x0:x1+1]; a=a[y0:y1+1,x0:x1+1]


def to_img(rgb,a):
    out=np.dstack([rgb,a*255]).clip(0,255).astype(np.uint8)
    return Image.fromarray(out,'RGBA')

# The wordmark is flat colour, so give it flat colour: this removes the JPEG fringing around the letters.
X_SPLIT=1142          # "Universities" ends and the blue "500" starts (crop coordinates)
X_WORD=440            # the wordmark starts here; the U mark is to the left
cols=np.arange(rgb.shape[1])[None,:,None]
word=cols>=X_WORD
blue_part=cols>=X_SPLIT
BLUE=np.array([33,171,246],float)
def flat(rgb_in, white_to):
    out=rgb_in.copy()
    out=np.where(word&~blue_part, np.array(white_to,float), out)
    out=np.where(word&blue_part, BLUE, out)
    return out
# crisp, filled edges for the flat wordmark (the JPEG leaves holes and speckle in the soft edge)
from scipy.ndimage import gaussian_filter
g=gaussian_filter(a,0.7)
t=np.clip((g-0.30)/(0.70-0.30),0,1); t=t*t*(3-2*t)
a=np.where(word[...,0],t,a)
rgb_dark=flat(rgb,(255,255,255))
# DARK theme: as designed (white + blues) on transparent
dark=to_img(rgb_dark,a); 

# LIGHT theme: swap the white/grey parts for navy, keep the blues
mx=rgb.max(axis=2); mn=rgb.min(axis=2)
s=np.where(mx>0,(mx-mn)/np.maximum(mx,1),0)
L=rgb.mean(axis=2)/255
w=np.clip(1-s/0.30,0,1)                       # 1 = white/grey, 0 = blue
NAVY=np.array([6,22,92],float); SOFT=np.array([70,110,190],float)
neu=NAVY+(SOFT-NAVY)*np.clip((1-L)*2.2,0,1)[...,None]
rgbL=rgb*(1-w[...,None])+neu*w[...,None]
rgbL=flat(rgbL,(6,22,92))
light=to_img(rgbL,a); 

from PIL import ImageDraw
H=160
def sized(im,h): return im.resize((round(im.width*h/im.height),h),Image.LANCZOS)
mk=lambda im: im.crop((0,0,415,im.height))          # the U mark, left of the wordmark
sized(dark,H).save('public/brand/full-dark.png',optimize=True)
sized(light,H).save('public/brand/full-light.png',optimize=True)
sized(mk(light),120).save('public/brand/mark-light.png',optimize=True)
S,pad=128,16                                          # favicon: the mark on a navy rounded square
mm=mk(dark); mm.thumbnail((S-2*pad,S-2*pad),Image.LANCZOS)
fav=Image.new('RGBA',(S*4,S*4),(0,0,0,0)); ImageDraw.Draw(fav).rounded_rectangle((0,0,S*4-1,S*4-1),radius=90,fill=(1,9,56,255))
fav=fav.resize((S,S),Image.LANCZOS); fav.alpha_composite(mm,((S-mm.width)//2,(S-mm.height)//2)); fav.save('public/favicon.png',optimize=True)
print('written',dark.size)
