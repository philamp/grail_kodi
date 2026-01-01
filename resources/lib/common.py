import xbmc
import xbmcgui
import xbmcvfs
#import xbmcaddon
import os
import urllib.request
import urllib.error
import json
#import time
import uuid

VERSION="20250808"

def fetch_installation_uid(addon):
    install_path = xbmcvfs.translatePath(addon.getAddonInfo("path"))
    uid_file = os.path.join(install_path, "addon_uuid.txt")

    if xbmcvfs.exists(uid_file):
        with xbmcvfs.File(uid_file) as f:
            return f.read().strip()

    unique_id = str(uuid.uuid4())
    with xbmcvfs.File(uid_file, "w") as f:
        f.write(unique_id)

    return unique_id

def kodi_version():
    build = xbmc.getInfoLabel("System.BuildVersion")
    kodi_major = int(build.split('.')[0]) if build else 0
    return kodi_major

def jgnotifCT(h, p, force = False, x = xbmc.LOGINFO, err = ""):
    latency = 300
    if any((word in h.lower() for word in ["error", "warn", "fail"])):
        type = xbmcgui.NOTIFICATION_ERROR
    else:
        type = xbmcgui.NOTIFICATION_INFO
    xbmcgui.Dialog().notification("JG}{ "+h,p,type,latency)
    xbmc.log(f"{h}: {p}: {err}", x)

def confirmPopinCT(title, message):
    dialog = xbmcgui.Dialog()
    return dialog.yesno(title, message, yeslabel="Yes", nolabel="No")

def askUserRestartCT(addedMsg=""):
    xbmcgui.Dialog().ok("JellyGrail| Restart needed", f"Please restart Kodi - {addedMsg}")

def get_base_urlCT(addon):
    jgip = addon.getSettingString("jgip")
    jgport = addon.getSettingInt("jgport")
    jgproxy = addon.getSettingString("jgproxy")

    if jgproxy != "0":
        base_url = jgproxy + "/api"
    else:
        base_url = f"http://{jgip}:{jgport}/api"

    return base_url

def get_base_ident_paramsCT(addon):
    return f"?token={addon.getSettingString("jgtoken")}&uid={fetch_installation_uid(addon)}"


def fetch_jg_info(monitor, base_url, path, params, optionalparams = None, timeout=5):

    
    url = base_url + path + params
    url += optionalparams if optionalparams is not None else ""

    try:
        xbmc.log(f"[context.kodi_grail] Fetch : {url}", xbmc.LOGINFO)
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = response.read().decode("utf-8")
        result = json.loads(data)
        return result

    except urllib.error.HTTPError as e:
        if e.code == 401:
            #xbmc.log("[context.kodi_grail] Unauthorized (401)", xbmc.LOGWARNING)
            monitor.jgnotif("WS| Auth error 401", f"{path}", True)
            return None

        elif e.code == 404:
            return None
        
        else:
            monitor.jgnotif("WS| Fetch failed", f"{e.code}:{path}", True, err = f"{e.code}:{e.reason}", x = xbmc.LOGERROR)
            #xbmc.log(f"[context.kodi_grail] Fetch failed {path}: {e.code}: {e.reason}", xbmc.LOGERROR)
            return None
        
    except Exception as e:
        monitor.jgnotif("WS| Not HTTP error", f"check log", True, err = f"{e}", x = xbmc.LOGERROR)
        #xbmc.log(f"[context.kodi_grail] Fetch failed {path}: {e}", xbmc.LOGERROR)
        return None

def fetch_jg_infoCT(base_url, path, params, optionalparams = None, timeout=5, json_data=None):

    
    url = base_url + path + params
    url += optionalparams if optionalparams is not None else ""

    try:
        headers = {}
        data = None

        if json_data is not None:
            data = json.dumps(json_data).encode("utf-8")
            headers["Content-Type"] = "application/json"
            method = "POST"
        else:
            method = "GET"

        request = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method=method
        )

        xbmc.log(f"[context.kodi_grail] Fetch : {url}", xbmc.LOGINFO)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read().decode("utf-8")
        result = json.loads(data)
        return result

    except urllib.error.HTTPError as e:
        if e.code == 401:
            #xbmc.log("[context.kodi_grail] Unauthorized (401)", xbmc.LOGWARNING)
            jgnotifCT("WS| Auth error 401", f"{path}", True)
            return None

        elif e.code == 404:
            return None
        
        else:
            jgnotifCT("WS| Fetch failed", f"{e.code}:{path}", True, err = f"{e.code}:{e.reason}", x = xbmc.LOGERROR)
            #xbmc.log(f"[context.kodi_grail] Fetch failed {path}: {e.code}: {e.reason}", xbmc.LOGERROR)
            return None
        
    except Exception as e:
        jgnotifCT("WS| Not HTTP error", f"check log", True, err = f"{e}", x = xbmc.LOGERROR)
        #xbmc.log(f"[context.kodi_grail] Fetch failed {path}: {e}", xbmc.LOGERROR)
        return None