# contextitem.py
import sys
from common import *



def jgnotif(h, p, force = False, x = xbmc.LOGINFO, err = ""):
    latency = 300
    xbmcgui.Dialog().notification("JellyGrail| "+h,p,xbmcgui.NOTIFICATION_INFO,latency)
    xbmc.log(f"{h}: {p}: {err}", x)

def deleteUidFile(addon):

    install_path = xbmcvfs.translatePath(addon.getAddonInfo("path"))
    uid_file = os.path.join(install_path, "addon_uuid.txt")

    try:
        xbmcvfs.delete(uid_file)
    except Exception as e:
        xbmc.log(f"[GrailContext] ERROR deleting file {uid_file}: {e}", xbmc.LOGERROR)

def setConfigToDefaults(addon):

    defaults = {
        "override_ssdp_settings": "false",
        "jgip": "0.0.0.0",
        "jgport": "0",
        "jgtoken": "0",
        "jgproxy": "0",
        "debug_mode": "true",
    }

    for key, val in defaults.items():

        # Addon.setSetting expects strings for values
        addon.setSetting(key, str(val))

        xbmc.log(f"[GrailContext] ERROR setting default for {key}: {e}", xbmc.LOGERROR)

'''
def safe_get(index, default=None):
    try:
        jgnotif("sys.argv", f"index={index}, value={sys.argv[index]}")
        return sys.argv[index]
    except Exception:
        return default
'''
def run():
    LOG = "[GrailContext]"
    addon = xbmcaddon.Addon()
    '''
    xbmcgui.Dialog().notification(
        "Kodi Grail",
        "}{ Actions clicked",
        icon=addon.getAddonInfo("icon"),
        time=3000
    )
    '''
    try:
        #action = safe_get(1, "unknown")
        #media_path = safe_get(2, "none")

        #xbmc.log(f"{LOG} called: action={action}, path={media_path}", xbmc.LOGINFO)

        dialog = xbmcgui.Dialog()
        retr = dialog.contextmenu(['Retrieve Only', 'Retrive & Keep', 'WAF Play', 'Reset Add-on', 'Cancel'])

        if retr == -1 or retr == 4:
            return
        if retr == 3:
            #xbmc.log(f"{LOG} User requested addon reset", xbmc.LOGINFO)
            deleteUidFile(addon)
            setConfigToDefaults(addon)
            jgnotif("Add-on config", "Reinitialized", True)
            askUserRestartCT("UID file deleted")

            return

        if retr == 0 or retr == 1 or retr == 2:
            title = xbmc.getInfoLabel("ListItem.Title") or "NOTITLE"
            dbid = xbmc.getInfoLabel("ListItem.DBID") or "NOID"
            dbtype = xbmc.getInfoLabel("ListItem.DBTYPE") or "NOVIDEOTYPE"

            message = (
                f"ID : {dbid}\n"
                f"Titre : {title}\n"
                f"Type : {dbtype}\n"
            )

            xbmcgui.Dialog().ok("JellyGrail", message)

    except Exception as e:
        xbmc.log(f"{LOG} ERROR: {e}", xbmc.LOGERROR)
        try:
            xbmcgui.Dialog().notification("Kodi Grail", f"Erreur : {e}", xbmcgui.NOTIFICATION_ERROR, 4000)
        except Exception:
            pass


if __name__ == "__main__":
    xbmc.log("[context.kodi_grail] contextitem run()", xbmc.LOGINFO)
    run()
