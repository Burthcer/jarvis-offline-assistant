"""V3-owned numbered target overlay. No input/focus, screenshots or polling idle."""
import ctypes,threading,time,queue
from ctypes import wintypes as w
from PIL import Image,ImageDraw,ImageFont
import numpy as np
from .legacy.island import WNDPROC,WNDCLASS,BITMAPINFOHEADER,BLEND,u32,gdi

def render(snapshot,selected=None):
    items=snapshot.items
    x=min(i.bounds[0] for i in items)-5;y=min(i.bounds[1] for i in items)-5
    right=max(i.bounds[2] for i in items)+5;bottom=max(i.bounds[3] for i in items)+5
    width,height=round(right-x),round(bottom-y)+46
    if width<=0 or height<=0 or width*height>12_000_000:raise ValueError('Overlay area is too large')
    image=Image.new('RGBA',(width,height));draw=ImageDraw.Draw(image)
    font=ImageFont.truetype(r'C:\Windows\Fonts\segoeui.ttf',17)
    for index,item in enumerate(items,1):
        a,b,c,d=(round(item.bounds[0]-x),round(item.bounds[1]-y),round(item.bounds[2]-x),round(item.bounds[3]-y))
        colour='#f2cc7f' if selected==item.identity else '#b7a1ee'
        draw.rounded_rectangle((a,b,c,d),radius=7,outline=colour,width=3)
        draw.rounded_rectangle((a+3,b+3,a+34,b+31),radius=7,fill='#201832',outline=colour,width=2)
        draw.text((a+11,b+5),str(index),font=font,fill='#f3f0e8')
    label=next((i.title for i in items if i.identity==selected),'Say a number. Say “cancel choices” to dismiss.')
    draw.rounded_rectangle((0,height-39,width-1,height-1),radius=9,fill='#201832')
    while len(label)>1 and draw.textlength(label,font=font)>width-22:label=label[:-2]+'…'
    draw.text((10,height-34),label,font=font,fill='#f3f0e8')
    return image,(round(x),round(y))

class TargetOverlay:
    def __init__(self,render=render,name='Choices',expires=15):
        self.render,self.name,self.expires_after=render,name,expires
        self.commands=queue.Queue();self.stop=threading.Event();self.ready=threading.Event();self.hwnd=None;self.error=None;self.frames=0
        self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start()
        if not self.ready.wait(2) or self.error:
            self.close();raise RuntimeError('Could not start the target overlay')
    def show(self,snapshot,selected=None):
        if self.stop.is_set():raise RuntimeError('Target overlay is closed')
        self.commands.put((snapshot,selected))
    def close(self,wait=True):
        self.stop.set();self.commands.put(None)
        if wait and threading.current_thread()!=self.thread:self.thread.join(2)
    def _run(self):
        screen=dc=bitmap=old=None;name='JarvisV4'+self.name+str(id(self));instance=None
        try:
            kernel=ctypes.windll.kernel32;kernel.GetModuleHandleW.restype=w.HMODULE;instance=kernel.GetModuleHandleW(None)
            u32.DestroyWindow.argtypes=[w.HWND];u32.UnregisterClassW.argtypes=[w.LPCWSTR,w.HINSTANCE]
            gdi.DeleteObject.argtypes=[ctypes.c_void_p];gdi.DeleteDC.argtypes=[w.HDC]
            u32.SetWindowPos.argtypes=[w.HWND,w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.UINT]
            try:u32.SetThreadDpiAwarenessContext.argtypes=[ctypes.c_void_p];u32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
            except AttributeError:pass
            def proc(hwnd,msg,wp,lp):
                if msg==0x84:return -1 # HTTRANSPARENT: even painted badges pass clicks through
                if msg==0x21:return 3  # MA_NOACTIVATE
                return u32.DefWindowProcW(hwnd,msg,wp,lp)
            self._proc=WNDPROC(proc)
            wc=WNDCLASS(0,self._proc,0,0,instance,None,None,None,None,name)
            if not u32.RegisterClassW(ctypes.byref(wc)):raise OSError('Cannot register overlay window')
            self.hwnd=u32.CreateWindowExW(0x80000|0x20|0x8|0x80|0x8000000,name,'Jarvis V4 target overlay',0x80000000,0,0,1,1,None,None,instance,None)
            if not self.hwnd:raise OSError('Cannot create overlay window')
            screen=u32.GetDC(None);dc=gdi.CreateCompatibleDC(screen)
            self.ready.set();msg=w.MSG();expires=0
            while not self.stop.is_set():
                while u32.PeekMessageW(ctypes.byref(msg),self.hwnd,0,0,1):u32.TranslateMessage(ctypes.byref(msg));u32.DispatchMessageW(ctypes.byref(msg))
                try:command=self.commands.get(timeout=.05)
                except queue.Empty:command='unchanged'
                if command is None:break
                if command!='unchanged':
                    snapshot,selected=command
                    image,position=self.render(snapshot,selected);width,height=image.size
                    if bitmap:
                        gdi.SelectObject(dc,old);gdi.DeleteObject(bitmap);bitmap=None
                    info=BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER),width,-height,1,32,0,0,0,0,0,0)
                    bits=ctypes.c_void_p();bitmap=gdi.CreateDIBSection(screen,ctypes.byref(info),0,ctypes.byref(bits),None,0)
                    if not bitmap:raise OSError('Cannot draw target overlay')
                    old=gdi.SelectObject(dc,bitmap)
                    array=np.asarray(image);rgb=array[...,:3].astype(np.uint16)*array[...,3:4]//255
                    pixels=np.dstack((rgb[...,2],rgb[...,1],rgb[...,0],array[...,3])).astype(np.uint8)
                    ctypes.memmove(bits,pixels.tobytes(),pixels.size)
                    size,origin,blend=w.SIZE(width,height),w.POINT(0,0),BLEND(0,0,255,1)
                    u32.SetWindowPos(self.hwnd,w.HWND(-1),*position,width,height,0x10|0x4)
                    if not u32.UpdateLayeredWindow(self.hwnd,screen,None,ctypes.byref(size),dc,ctypes.byref(origin),0,ctypes.byref(blend),2):raise OSError('Could not display target overlay')
                    u32.ShowWindow(self.hwnd,8);self.frames+=1;expires=time.monotonic()+self.expires_after if self.expires_after else 0
                if expires and time.monotonic()>expires:u32.ShowWindow(self.hwnd,0);expires=0
        except Exception as error:self.error=str(error)
        finally:
            self.ready.set()
            if bitmap:gdi.SelectObject(dc,old);gdi.DeleteObject(bitmap)
            if dc:gdi.DeleteDC(dc)
            if screen:u32.ReleaseDC(None,screen)
            if self.hwnd:u32.DestroyWindow(self.hwnd);self.hwnd=None
            if instance:u32.UnregisterClassW(name,instance)
