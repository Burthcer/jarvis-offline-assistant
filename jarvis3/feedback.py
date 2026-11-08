"""Distinct cues and bounded timing events. A wake probe never authorises an action."""
from collections import deque
import threading,time
import numpy as np

def cue_audio(kind,rate=24000):
    frequencies={'wake':(880,),'success':(1046,1397),'error':(330,220)}[kind]
    parts=[]
    for frequency in frequencies:
        t=np.arange(round(rate*.065))/rate
        envelope=np.sin(np.pi*np.arange(len(t))/max(1,len(t)-1))**2
        parts.append((np.sin(2*np.pi*frequency*t)*envelope*.16*32767).astype(np.int16))
        parts.append(np.zeros(round(rate*.018),np.int16))
    return np.concatenate(parts)

class Feedback:
    def __init__(self,send=lambda kind,token,started:False,clock=time.perf_counter):
        self.send,self.clock=send,clock
        self.events=deque(maxlen=160);self.seen=deque(maxlen=160);self.lock=threading.RLock();self.serial=0
    def record(self,event,token,**fields):
        with self.lock:self.events.append({'event':event,'request':str(token),'at':self.clock(),**fields})
    def begin(self):
        with self.lock:self.serial+=1;token='command-'+str(self.serial)
        self.record('accepted',token)
        return token
    def cue(self,kind,token):
        key=(kind,str(token))
        with self.lock:
            if key in self.seen:return False
            self.seen.append(key)
        self.record(kind+'-detected',token)
        queued=self.send(kind,token,lambda:self.record(kind+'-output-start',token))
        self.record(kind+'-queued' if queued else kind+'-silent',token)
        return queued
    def snapshot(self):
        with self.lock:return [dict(e) for e in list(self.events)[-30:]]
