import json
from effects import catalog
from palettes import PALETTES
from utils import number
class API:
    def __init__(self,engine): self.engine=engine
    def handle(self,method,path,body=b''):
        e=self.engine
        try:
            if method=='GET':
                if path=='/api/state': return 200,e.state()
                if path=='/api/effects': return 200,catalog()
                if path=='/api/palettes': return 200,list(PALETTES)
                if path=='/api/presets': return 200,e.store.all()
                if path=='/api/playlist': return 200,e.state()['playlist']
            if method=='POST':
                if path=='/api/frame': e.frame(body);return 200,{'ok':True}
                value=json.loads(body.decode('utf-8'))
                if path=='/api/state': e.apply(value);e.playlist_running=False
                elif path=='/api/preset':
                    e.apply_preset(value['name']);e.playlist_running=False
                elif path=='/api/playlist': e.set_playlist(value)
                elif path=='/api/save': e.save(value.get('name'))
                elif path=='/api/audio':
                    e.audio.push(value['levels'],value.get('bands'),value.get('waveform'))
                elif path=='/api/audio/config':
                    if not isinstance(value,dict) or set(value)-set(('gain','gate','agc')): raise ValueError('Invalid audio config')
                    gain=number(value.get('gain',e.audio.gain),0,4)
                    gate=number(value.get('gate',e.audio.gate),0,.5)
                    agc=value.get('agc',e.audio.agc)
                    if not isinstance(agc,bool): raise ValueError('agc must be boolean')
                    e.audio.gain=gain;e.audio.gate=gate;e.audio.agc=agc
                else: return 404,{'error':'Not found'}
                return 200,{'ok':True}
            return 404,{'error':'Not found'}
        except (ValueError,KeyError,TypeError,IndexError,AttributeError) as error:
            return 400,{'error':str(error)}
        except MemoryError:
            return 503,{'error':'Not enough free memory'}
        except OSError:
            return 503,{'error':'Storage unavailable'}
