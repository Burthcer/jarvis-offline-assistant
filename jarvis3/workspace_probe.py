"""Read only exact configured folder identity, with a bounded Shell helper.

Shell.Windows: https://learn.microsoft.com/windows/win32/shell/shell-windows
No contents, titles, navigation, clipboard or foreground changes.
"""
import json,ntpath,os,subprocess,sys

def native_folder(target,shell=None):
    if shell is None:
        import comtypes.client
        shell=comtypes.client.CreateObject('Shell.Application',dynamic=True)
    windows=shell.Windows();count=int(windows.Count)
    if not 0<=count<=128:return None
    wanted=ntpath.normcase(ntpath.normpath(target))
    incomplete=False
    for i in range(count):
        try:
            item=windows.Item(i)
            if ntpath.basename(str(item.FullName)).lower()!='explorer.exe':continue
            path=str(item.Document.Folder.Self.Path)
            if ntpath.normcase(ntpath.normpath(path))==wanted:
                # Provider may navigate between reads. Match twice, not the title.
                return True if str(item.Document.Folder.Self.Path)==path else None
        except Exception:incomplete=True
    return None if incomplete or int(windows.Count)!=count else False

def folder(target):
    from .paths import PROJECT
    try:
        r=subprocess.run([sys.executable,'-m','jarvis3.workspace_probe',target],cwd=PROJECT,env={**os.environ,'JARVIS_SILENT':'1'},capture_output=True,text=True,timeout=1.5,creationflags=subprocess.CREATE_NO_WINDOW)
        result=json.loads(r.stdout)
        return result if type(result) is bool else None
    except (OSError,ValueError,subprocess.TimeoutExpired):return None

if __name__=='__main__':
    try:result=native_folder(sys.argv[1])
    except Exception:result=None
    print(json.dumps(result),flush=True)
