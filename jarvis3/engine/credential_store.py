"""Windows Credential Manager, current user only. Never log credential data."""
import ctypes,json
from ctypes import wintypes as w
class Credential(ctypes.Structure):
    _fields_=[('Flags',w.DWORD),('Type',w.DWORD),('TargetName',w.LPWSTR),('Comment',w.LPWSTR),('LastWritten',w.FILETIME),('CredentialBlobSize',w.DWORD),('CredentialBlob',ctypes.POINTER(ctypes.c_ubyte)),('Persist',w.DWORD),('AttributeCount',w.DWORD),('Attributes',ctypes.c_void_p),('TargetAlias',w.LPWSTR),('UserName',w.LPWSTR)]
TARGET='JarvisOfflineAssistant/V4/GoogleReadOnly'
def put(value):
    data=json.dumps(value).encode('utf-8')
    if len(data)>2560:raise ValueError('Google credential is too large for the secure Windows store.')
    buf=(ctypes.c_ubyte*len(data)).from_buffer_copy(data)
    credential=Credential(Type=1,TargetName=TARGET,CredentialBlobSize=len(data),CredentialBlob=buf,Persist=2,UserName='Jarvis')
    fn=ctypes.windll.advapi32.CredWriteW; fn.argtypes=[ctypes.POINTER(Credential),w.DWORD]
    if not fn(ctypes.byref(credential),0):raise OSError('Windows could not securely save the connection.')
def get():
    pointer=ctypes.POINTER(Credential)()
    fn=ctypes.windll.advapi32.CredReadW;fn.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,ctypes.POINTER(ctypes.POINTER(Credential))]
    if not fn(TARGET,1,0,ctypes.byref(pointer)):return None
    free=ctypes.windll.advapi32.CredFree;free.argtypes=[ctypes.c_void_p]
    try:return json.loads(ctypes.string_at(pointer.contents.CredentialBlob,pointer.contents.CredentialBlobSize).decode('utf-8'))
    finally:free(pointer)
def remove():
    fn=ctypes.windll.advapi32.CredDeleteW;fn.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD]
    fn(TARGET,1,0)
