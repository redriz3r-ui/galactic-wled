import json
import os
import config

def preset(name,effect,palette,speed=.35,brightness=.45,**params):
    params['speed']=speed
    return {'name':name,'effect':effect,'palette':palette,'brightness':brightness,'params':params,'layers':[],'audio_reactive':True}
DEFAULTS=[
    preset('Moody R&B','plasma','midnight',.22,.45,intensity=.72,audio_amount=.65),
    preset('Midnight Drive','freqwave','blue_noir',.35),
    preset('Dreamscape','metaballs','purple_haze',.2,intensity=.65),
    preset('Club','center_pulse','neon',.75,.55),
    preset('Spectrum','spectrum','audio_spectrum',.4),
    preset('Cassette Night','cassette','warm_sunset',.3),
    preset('Ambient','plasma','ocean',.15,audio_amount=.25),
    preset('Cyberpunk','spectral_history','cyberpunk',.5),
    preset('Sunset','sunrise','sunrise',.6),
    preset('Matrix','digital_rain','matrix',.4),
    preset('Fire','fire','fire',.4),
    preset('Chill','rain','ice',.25),
    preset('Passing Lights','passing_lights','warm_sunset',.35)]
DEFAULTS[0]['layers']=[{'effect':'particles','palette':'purple_haze','blend':'add','opacity':.25,'zone':'full','params':{'density':.12,'intensity':.45,'trail':.5}}]
SHOWCASE={'items':[{'preset':n,'duration':30,'transition':1.5} for n in ('Moody R&B','Cassette Night','Dreamscape','Midnight Drive')],'loop':True}
class Store:
    def __init__(self,path=None):
        self.path=path or config.SETTINGS_FILE
        self.user=[];self.saved=None
        try:
            with open(self.path) as f: d=json.load(f)
            if isinstance(d,dict):
                self.user=d.get('presets',[])[:12] if isinstance(d.get('presets'),list) else []
                self.saved=d.get('state')
        except (OSError,ValueError,TypeError):
            self.saved=None
    def all(self): return DEFAULTS+self.user
    def get(self,name):
        for p in self.all():
            if isinstance(p,dict) and p.get('name')==name: return p
        raise ValueError('Unknown preset')
    def write(self,state):
        tmp=self.path+'.tmp'
        with open(tmp,'w') as f: json.dump({'version':1,'state':state,'presets':self.user},f)
        os.rename(tmp,self.path)
        self.saved=state
