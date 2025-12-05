import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon
import os
import urllib.request
import urllib.error
import json

VERSION="20250808"

def kodi_version():
    build = xbmc.getInfoLabel("System.BuildVersion")
    kodi_major = int(build.split('.')[0]) if build else 0
    return kodi_major

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
    return f"?token={addon.getSettingString("jgtoken")}"


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