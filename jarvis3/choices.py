"""Deterministic, expiring choice snapshots shared by native selection adapters."""
from dataclasses import dataclass
import time,uuid
from .engine.uia import risky
@dataclass(frozen=True)
class Item:
    identity:str
    title:str
    bounds:tuple
@dataclass(frozen=True)
class Snapshot:
    token:str
    page:tuple
    group:str
    at:float
    items:tuple
class Choices:
    def __init__(self,clock=time.monotonic):self.clock=clock;self.snapshot=None;self.preview=None
    def capture(self,page,group,items,viewport):
        left,top,right,bottom=viewport;visible=[];seen={}
        if right<=left or bottom<=top:raise ValueError('Invalid visible area')
        for raw in items:
            if not raw.get('visible') or not raw.get('enabled') or raw.get('password') or raw.get('group')!=group:continue
            title=str(raw.get('title','')).strip()
            if not title or risky(title):continue
            x,y,r,b=tuple(raw['bounds'])
            if r<=x or b<=y or min(r,right)<=max(x,left) or min(b,bottom)<=max(y,top):continue
            # A small clipped corner must not become an offered on-screen choice.
            area=(min(r,right)-max(x,left))*(min(b,bottom)-max(y,top))
            if area<(r-x)*(b-y)*.5:continue
            item=Item(str(raw['id']),title,(x,y,r,b))
            if not item.identity:raise ValueError('Missing stable item identity')
            if item.identity in seen:
                if seen[item.identity]!=item:raise ValueError('Ambiguous item identity')
                continue
            seen[item.identity]=item;visible.append(item)
        # Group rows first, then read left-to-right within each row.
        ordered=[];rows=[]
        for item in sorted(visible,key=lambda i:(i.bounds[1],i.bounds[0])):
            row=next((row for row in rows if abs(row[0].bounds[1]-item.bounds[1])<=8),None)
            if row is None:rows.append([item])
            else:row.append(item)
        for row in rows:ordered.extend(sorted(row,key=lambda i:i.bounds[0]))
        if not ordered or len(ordered)>20:raise ValueError('Choose a smaller visible group')
        self.snapshot=Snapshot(uuid.uuid4().hex,tuple(page),group,self.clock(),tuple(ordered));self.preview=None
        return self.snapshot
    def resolve(self,selector):
        snap=self.snapshot
        if snap is None or self.clock()-snap.at>15:raise ValueError('Choices expired; refresh them')
        if type(selector)==int:
            if not 1<=selector<=len(snap.items):raise ValueError('That position is not visible')
            index=selector-1
        else:
            hits=[i for i,item in enumerate(snap.items) if str(selector).strip().lower() in item.title.lower()]
            if not str(selector).strip() or len(hits)!=1:raise ValueError('Please choose one numbered item')
            index=hits[0]
        self.preview=(snap.token,index);return snap.items[index]
    def commit(self,fresh,invoke,confirmed=False,verify=lambda item:False):
        snap=self.snapshot
        if not confirmed or not snap or not self.preview or self.clock()-snap.at>15:raise ValueError('A fresh target preview and confirmation are required')
        if self.preview[0]!=snap.token or (fresh.page,fresh.group,fresh.items)!=(snap.page,snap.group,snap.items):
            self.preview=None;raise ValueError('The page or choices changed; refresh them')
        item=snap.items[self.preview[1]];self.preview=None # consume BEFORE invoking; cannot repeat on error
        if not invoke(item):return {'requested':False,'verified':False,'title':item.title}
        return {'requested':True,'verified':verify(item) is True,'title':item.title}
