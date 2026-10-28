"""Real foreground ownership and setup-only activation; never refocus a measurement."""
import ctypes
import time
from ctypes import wintypes


def activate_browser_window(expected_process):
    """Activate this test's visible browser once, before fullscreen/measurement."""
    user32=ctypes.WinDLL('user32',use_last_error=True)
    kernel32=ctypes.WinDLL('kernel32',use_last_error=True)
    user32.GetForegroundWindow.restype=wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user32.IsWindowVisible.argtypes=[wintypes.HWND]
    user32.SetForegroundWindow.argtypes=[wintypes.HWND]
    user32.BringWindowToTop.argtypes=[wintypes.HWND]
    user32.SetActiveWindow.argtypes=[wintypes.HWND]
    user32.SetFocus.argtypes=[wintypes.HWND]
    user32.AttachThreadInput.argtypes=[wintypes.DWORD,wintypes.DWORD,wintypes.BOOL]
    user32.PeekMessageW.argtypes=[ctypes.POINTER(wintypes.MSG),wintypes.HWND,wintypes.UINT,wintypes.UINT,wintypes.UINT]
    message=wintypes.MSG()
    # Explicitly create the caller's queue before attaching input threads.
    # https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-attachthreadinput
    user32.PeekMessageW(ctypes.byref(message),None,0x400,0x400,0)
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    candidates=[]
    def collect(handle,_):
        owner=wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle,ctypes.byref(owner))
        if owner.value==expected_process and user32.IsWindowVisible(handle):
            candidates.append(handle)
        return True
    callback=callback_type(collect)
    user32.EnumWindows(callback,0)
    if len(candidates)!=1:
        raise RuntimeError('Expected exactly one visible benchmark browser window: '+str(candidates))
    current=kernel32.GetCurrentThreadId()
    target_thread=user32.GetWindowThreadProcessId(candidates[0],None)
    attachment_errors=[]
    for attempt in range(5):
        foreground_thread=user32.GetWindowThreadProcessId(user32.GetForegroundWindow(),None)
        attached=[]
        try:
            for thread in {foreground_thread,target_thread}-{0,current}:
                if user32.AttachThreadInput(current,thread,True):attached.append(thread)
                else:attachment_errors.append(dict(thread=thread,error=ctypes.get_last_error()))
            user32.BringWindowToTop(candidates[0])
            user32.SetActiveWindow(candidates[0])
            user32.SetForegroundWindow(candidates[0])
            user32.SetFocus(candidates[0])
        finally:
            for thread in reversed(attached):user32.AttachThreadInput(current,thread,False)
        time.sleep(.1)
        try:
            state=foreground_window(expected_process)
            state['attachmentErrors']=attachment_errors
            return state
        except RuntimeError as error:
            if attempt==4:
                raise RuntimeError(str(error)+'; input attachment errors: '+str(attachment_errors)) from error


def wait_foreground_window(expected_process,timeout_seconds=180,poll=None):
    """Wait for the operator's real click; never emulate or steal focus."""
    started=time.monotonic()
    announced=False
    while True:
        try:
            state=foreground_window(expected_process)
            state['waitedSeconds']=time.monotonic()-started
            return state
        except RuntimeError:
            if time.monotonic()-started>=timeout_seconds:raise
            if not announced:
                print('WAITING_FOR_REAL_WINDOWS_FOREGROUND_CLICK',expected_process,flush=True)
                announced=True
            (poll or time.sleep)(.25)



def foreground_window(expected_process):
    user32=ctypes.WinDLL('user32',use_last_error=True)
    user32.GetForegroundWindow.restype=wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user32.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    handle=user32.GetForegroundWindow()
    owner=wintypes.DWORD()
    user32.GetWindowThreadProcessId(handle,ctypes.byref(owner))
    rect=wintypes.RECT()
    if not user32.GetClientRect(handle,ctypes.byref(rect)):
        raise RuntimeError('Windows could not inspect the actual foreground client')
    state=dict(hwnd=handle,ownerProcessId=owner.value,expectedProcessId=expected_process,
               clientSize=[rect.right-rect.left,rect.bottom-rect.top])
    if owner.value!=expected_process:
        raise RuntimeError('Benchmark browser lost real Windows foreground focus: '+str(state))
    return state
