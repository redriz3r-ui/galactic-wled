"""Registry is metadata; implementations share one compact, lazily imported module."""
DEFAULTS={'speed':.35,'intensity':.7,'scale':.5,'sensitivity':.6,'trail':.35,
          'decay':.5,'density':.4,'blur':.3,'direction':1,'audio_amount':.6,
          'mirrored':True,'scrolling':False,'center_line':False}
COMMON=('speed','intensity','audio_amount','sensitivity','trail')
EXTRAS={
'plasma':('scale',),'waveform':('scale','mirrored','scrolling','center_line'),
'spectrum':('decay',),'freqwave':('scale',),'spectral_history':('direction',),
'cassette':('scale',),'center_pulse':('decay',),'particles':('density','direction'),
'starfield':('density','direction'),'digital_rain':('density',),'fire':('scale',),
'metaballs':('scale','blur'),'rain':('density',),'sunrise':(),
'passing_lights':()}
NAMES=tuple(EXTRAS)
def catalog():
    result=[]
    for name in NAMES:
        supported=COMMON+EXTRAS[name]
        if name in ('plasma','spectrum','spectral_history','fire','metaballs','sunrise','passing_lights'):
            supported=tuple(k for k in supported if k!='trail')
        if name=='sunrise': supported=('speed','intensity')
        result.append({'id':name,'parameters':supported})
    return result
def resolve(name):
    if name=='passing_lights':
        from effects.passing_lights import render
        return render
    from effects import library
    return getattr(library,name)
