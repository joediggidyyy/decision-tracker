"""Small Windows adapters: current-user ACLs, DPAPI and local-only framed named pipes."""
import ctypes as C
from ctypes import wintypes as W
import json,os,time,threading
from pathlib import Path
from .errors import Fault,require

def windows():require(os.name=='nt','UNSUPPORTED_PLATFORM','This local adapter requires Windows.',503)
def libs():
    windows();return C.WinDLL('kernel32',use_last_error=True),C.WinDLL('advapi32',use_last_error=True)
def check(ok):
    if not ok:raise OSError(C.get_last_error(),'Windows local security operation failed.')
def owner_sid():
    k,a=libs();token=W.HANDLE()
    a.OpenProcessToken.argtypes=[W.HANDLE,W.DWORD,C.POINTER(W.HANDLE)]
    k.GetCurrentProcess.restype=W.HANDLE
    check(a.OpenProcessToken(k.GetCurrentProcess(),8,C.byref(token)))
    try:return token_sid(token)
    finally:k.CloseHandle(token)
def token_sid(token):
    k,a=libs();size=W.DWORD();a.GetTokenInformation(token,1,None,0,C.byref(size));buf=C.create_string_buffer(size.value)
    check(a.GetTokenInformation(token,1,buf,size,C.byref(size)))
    sid=C.cast(buf,C.POINTER(C.c_void_p))[0];value=W.LPWSTR()
    a.ConvertSidToStringSidW.argtypes=[C.c_void_p,C.POINTER(W.LPWSTR)]
    check(a.ConvertSidToStringSidW(sid,C.byref(value)))
    try:return value.value
    finally:k.LocalFree(C.cast(value,C.c_void_p))
def descriptor():
    k,a=libs();sd=C.c_void_p()
    a.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes=[W.LPCWSTR,W.DWORD,C.POINTER(C.c_void_p),C.c_void_p]
    check(a.ConvertStringSecurityDescriptorToSecurityDescriptorW('D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;'+owner_sid()+')',1,C.byref(sd),None))
    return sd

def protect_path(path):
    k,a=libs();sd=descriptor()
    try:
        a.SetFileSecurityW.argtypes=[W.LPCWSTR,W.DWORD,C.c_void_p]
        check(a.SetFileSecurityW(str(path),0x80000004,sd))
    finally:k.LocalFree(sd)

class Blob(C.Structure):_fields_=[('size',W.DWORD),('data',C.POINTER(C.c_ubyte))]
def dpapi(raw,decrypt=False):
    windows();crypt=C.WinDLL('crypt32',use_last_error=True);k,_=libs();buf=(C.c_ubyte*len(raw)).from_buffer_copy(raw);source=Blob(len(raw),buf);result=Blob()
    if decrypt:
        crypt.CryptUnprotectData.argtypes=[C.POINTER(Blob),C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,W.DWORD,C.POINTER(Blob)]
        ok=crypt.CryptUnprotectData(C.byref(source),None,None,None,None,1,C.byref(result))
    else:
        crypt.CryptProtectData.argtypes=[C.POINTER(Blob),W.LPCWSTR,C.c_void_p,C.c_void_p,C.c_void_p,W.DWORD,C.POINTER(Blob)]
        ok=crypt.CryptProtectData(C.byref(source),'Decision Tracker',None,None,None,1,C.byref(result))
    check(ok)
    try:return C.string_at(result.data,result.size)
    finally:k.LocalFree(result.data)

def save_bundle(path,value):
    raw=dpapi(json.dumps(value,separators=(',',':')).encode())
    temp=path.with_name(path.name+'.'+__import__('uuid').uuid4().hex+'.pending')
    with temp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    protect_path(temp);temp.replace(path)

def read_bundle(path):
    require(path.is_file() and not path.is_symlink() and not path.is_junction(),'SETUP_REQUIRED','Protected local credentials are unavailable.',503)
    require(path.stat().st_size<=65536,'SETUP_REQUIRED','Protected credential store is invalid.',503)
    try:return json.loads(dpapi(path.read_bytes(),True))
    except (OSError,ValueError):raise Fault('SETUP_REQUIRED','Protected local credentials could not be opened.',503) from None

class SecurityAttributes(C.Structure):_fields_=[('length',W.DWORD),('descriptor',C.c_void_p),('inherit',W.BOOL)]
def pipe_name(deployment):return r'\\.\pipe\decision-tracker-admin-'+str(__import__('uuid').UUID(deployment))
def pipe_api():
    k,a=libs()
    k.CreateNamedPipeW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,W.DWORD,W.DWORD,W.DWORD,W.DWORD,C.POINTER(SecurityAttributes)];k.CreateNamedPipeW.restype=W.HANDLE
    k.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE];k.CreateFileW.restype=W.HANDLE
    k.ReadFile.argtypes=[W.HANDLE,C.c_void_p,W.DWORD,C.POINTER(W.DWORD),C.c_void_p]
    k.WriteFile.argtypes=k.ReadFile.argtypes
    k.CloseHandle.argtypes=[W.HANDLE];k.ConnectNamedPipe.argtypes=[W.HANDLE,C.c_void_p];k.DisconnectNamedPipe.argtypes=[W.HANDLE]
    k.SetNamedPipeHandleState.argtypes=[W.HANDLE,C.POINTER(W.DWORD),C.c_void_p,C.c_void_p]
    return k,a

def transfer(handle,write=None):
    k,_=pipe_api();deadline=time.monotonic()+10
    if write is not None:
        data=json.dumps(write,separators=(',',':')).encode();require(len(data)<=16384,'LIMIT_EXCEEDED','Local request is too large.',413)
        data=len(data).to_bytes(4,'little')+data;offset=0
        while offset<len(data):
            count=W.DWORD();chunk=C.create_string_buffer(data[offset:]);ok=k.WriteFile(handle,chunk,len(data)-offset,C.byref(count),None)
            if ok:offset+=count.value
            elif C.get_last_error()!=232:check(False)
            require(time.monotonic()<deadline,'SERVICE_UNAVAILABLE','Local request timed out.',503);time.sleep(.005)
        return
    data=bytearray();size=4
    while len(data)<size:
        buf=C.create_string_buffer(min(4096,size-len(data)));count=W.DWORD();ok=k.ReadFile(handle,buf,len(buf),C.byref(count),None)
        if ok:data.extend(buf.raw[:count.value])
        elif C.get_last_error() not in (232,536):check(False)
        require(time.monotonic()<deadline,'SERVICE_UNAVAILABLE','Local request timed out.',503)
        if len(data)==4 and size==4:
            size=4+int.from_bytes(data,'little');require(4<size<=16388,'LIMIT_EXCEEDED','Invalid local frame.',413)
        time.sleep(.005)
    return json.loads(data[4:])

class AdminPipe:
    def __init__(self,deployment,callback):self.deployment=deployment;self.callback=callback;self.stop_event=threading.Event();self.thread=None;self.handle=None
    def start(self):
        k,_=pipe_api();sd=descriptor();sa=SecurityAttributes(C.sizeof(SecurityAttributes),sd,False)
        try:self.handle=k.CreateNamedPipeW(pipe_name(self.deployment),0x00080003,0x00000009,1,32768,32768,0,C.byref(sa))
        finally:k.LocalFree(sd)
        check(self.handle!=W.HANDLE(-1).value)
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def run(self):
        k,a=pipe_api()
        while not self.stop_event.is_set():
            connected=k.ConnectNamedPipe(self.handle,None);err=C.get_last_error()
            if not connected and err not in (535,):time.sleep(.02);continue
            try:
                request=transfer(self.handle)
                a.ImpersonateNamedPipeClient.argtypes=[W.HANDLE];check(a.ImpersonateNamedPipeClient(self.handle))
                token=W.HANDLE()
                try:
                    k.GetCurrentThread.restype=W.HANDLE
                    a.OpenThreadToken.argtypes=[W.HANDLE,W.DWORD,W.BOOL,C.POINTER(W.HANDLE)]
                    check(a.OpenThreadToken(k.GetCurrentThread(),8,True,C.byref(token)));sid=token_sid(token)
                finally:
                    if token:k.CloseHandle(token)
                    a.RevertToSelf()
                require(sid==owner_sid(),'FORBIDDEN','Local owner access required.',403)
                require(isinstance(request,dict) and request.get('version')==1 and request.get('deployment_id')==self.deployment,'FORBIDDEN','Wrong local deployment.',403)
                result=self.callback(request)
                transfer(self.handle,{'ok':True,'data':result})
            except Fault as exc:
                try:transfer(self.handle,{'ok':False,'error':{'code':exc.code,'message':exc.message,'status':exc.status}})
                except Exception:pass
            except Exception:
                try:transfer(self.handle,{'ok':False,'error':{'code':'LOCAL_ADMIN_FAILED','message':'Local administration failed.','status':503}})
                except Exception:pass
            finally:
                try:transfer(self.handle)  # bounded client acknowledgement before disconnect
                except Exception:pass
                k.DisconnectNamedPipe(self.handle)
        k.CloseHandle(self.handle)
    def close(self):
        self.stop_event.set()
        if self.thread:self.thread.join(11)

def admin_request(deployment,operation,**values):
    k,a=pipe_api();deadline=time.monotonic()+10
    while True:
        handle=k.CreateFileW(pipe_name(deployment),0xC0000000,0,None,3,0,None)
        if handle!=W.HANDLE(-1).value:break
        if C.get_last_error()!=231 or time.monotonic()>=deadline:check(False)
        time.sleep(.02)
    try:
        # Verify the server process before sending any credential-bearing frame.
        pid=W.DWORD();k.GetNamedPipeServerProcessId.argtypes=[W.HANDLE,C.POINTER(W.DWORD)]
        check(k.GetNamedPipeServerProcessId(handle,C.byref(pid)))
        k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
        process=k.OpenProcess(0x1000,False,pid.value);check(process)
        token=W.HANDLE()
        try:
            a.OpenProcessToken.argtypes=[W.HANDLE,W.DWORD,C.POINTER(W.HANDLE)]
            check(a.OpenProcessToken(process,8,C.byref(token)))
            require(token_sid(token)==owner_sid(),'FORBIDDEN','Local administration server belongs to another owner.',403)
        finally:
            if token:k.CloseHandle(token)
            k.CloseHandle(process)
        mode=W.DWORD(1);check(k.SetNamedPipeHandleState(handle,C.byref(mode),None,None))
        transfer(handle,{'version':1,'deployment_id':deployment,'operation':operation,**values});result=transfer(handle)
        transfer(handle,{'received':True})
        if not result.get('ok'):
            err=result['error'];raise Fault(err['code'],err['message'],err['status'])
        return result['data']
    finally:k.CloseHandle(handle)
