"""Functional-only readback of the foreground test canvas from the real desktop.

Never import/call from performance runners. Capture only the verified test
browser's canvas rectangle, with foreground ownership checked before and after.
"""
import ctypes
from ctypes import wintypes
import hashlib
import math
import struct
import zlib
from phase45_window_focus import foreground_window


def capture_foreground_canvas(expected_process,bounds,destination):
    user32=ctypes.WinDLL('user32',use_last_error=True)
    gdi32=ctypes.WinDLL('gdi32',use_last_error=True)
    user32.GetDC.argtypes=[wintypes.HWND];user32.GetDC.restype=wintypes.HDC
    user32.ReleaseDC.argtypes=[wintypes.HWND,wintypes.HDC]
    user32.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
    user32.IsIconic.argtypes=[wintypes.HWND]
    user32.SetThreadDpiAwarenessContext.argtypes=[wintypes.HANDLE]
    user32.SetThreadDpiAwarenessContext.restype=wintypes.HANDLE
    gdi32.CreateCompatibleDC.argtypes=[wintypes.HDC];gdi32.CreateCompatibleDC.restype=wintypes.HDC
    gdi32.CreateDIBSection.argtypes=[wintypes.HDC,ctypes.c_void_p,wintypes.UINT,ctypes.POINTER(ctypes.c_void_p),wintypes.HANDLE,wintypes.DWORD]
    gdi32.CreateDIBSection.restype=wintypes.HANDLE
    gdi32.SelectObject.argtypes=[wintypes.HDC,wintypes.HANDLE];gdi32.SelectObject.restype=wintypes.HANDLE
    gdi32.BitBlt.argtypes=[wintypes.HDC,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.HDC,ctypes.c_int,ctypes.c_int,wintypes.DWORD]
    gdi32.DeleteObject.argtypes=[wintypes.HANDLE];gdi32.DeleteDC.argtypes=[wintypes.HDC]
    class Header(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('width',wintypes.LONG),('height',wintypes.LONG),
            ('planes',wintypes.WORD),('bits',wintypes.WORD),('compression',wintypes.DWORD),
            ('imageSize',wintypes.DWORD),('xppm',wintypes.LONG),('yppm',wintypes.LONG),
            ('used',wintypes.DWORD),('important',wintypes.DWORD)]
    class Info(ctypes.Structure):
        _fields_=[('header',Header),('color',wintypes.DWORD)]
    prior_dpi=user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    screen=memory=bitmap=previous=None
    try:
        before=foreground_window(expected_process)
        assert not user32.IsIconic(before['hwnd']),'Physical test window is minimized'
        origin=wintypes.POINT()
        assert user32.ClientToScreen(before['hwnd'],ctypes.byref(origin))
        sx=before['clientSize'][0]/bounds['viewportWidth'];sy=before['clientSize'][1]/bounds['viewportHeight']
        left,top=round(bounds['x']*sx),round(bounds['y']*sy)
        width,height=round(bounds['width']*sx),round(bounds['height']*sy)
        assert width>0 and height>0 and left>=0 and top>=0
        assert left+width<=before['clientSize'][0] and top+height<=before['clientSize'][1]
        screen=user32.GetDC(None);assert screen
        memory=gdi32.CreateCompatibleDC(screen);assert memory
        info=Info();info.header=Header(ctypes.sizeof(Header),width,-height,1,32,0,width*height*4,0,0,0,0)
        pixels=ctypes.c_void_p()
        bitmap=gdi32.CreateDIBSection(screen,ctypes.byref(info),0,ctypes.byref(pixels),None,0);assert bitmap and pixels.value
        previous=gdi32.SelectObject(memory,bitmap);assert previous
        assert gdi32.BitBlt(memory,0,0,width,height,screen,origin.x+left,origin.y+top,0x40CC0020)
        raw=ctypes.string_at(pixels,width*height*4)
        after=foreground_window(expected_process)
        assert before==after,'Physical canvas moved or lost foreground during capture'
    finally:
        if previous and memory:gdi32.SelectObject(memory,previous)
        if bitmap:gdi32.DeleteObject(bitmap)
        if memory:gdi32.DeleteDC(memory)
        if screen:user32.ReleaseDC(None,screen)
        if prior_dpi:user32.SetThreadDpiAwarenessContext(prior_dpi)
    rgb=bytearray(width*height*3)
    rgb[0::3]=raw[2::4];rgb[1::3]=raw[1::4];rgb[2::3]=raw[0::4]
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    rows=b''.join(b'\0'+rgb[row*width*3:(row+1)*width*3] for row in range(height))
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows,1))+chunk(b'IEND',b'')
    destination.write_bytes(png)
    deviations=[]
    for channel in range(3):
        samples=rgb[channel::3*64];mean=sum(samples)/len(samples)
        deviations.append(math.sqrt(sum((value-mean)**2 for value in samples)/len(samples)))
    return dict(file=str(destination),SHA256=hashlib.sha256(png).hexdigest(),width=width,height=height,
        deviationRGB=deviations,foregroundWindow=before,
        scope='Single real desktop canvas readback in functional lifecycle test only; never a performance measurement')
