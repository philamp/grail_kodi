# contextitem.py
import sys
from common import *



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
        jgnotifCT("sys.argv", f"index={index}, value={sys.argv[index]}")
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
        retr = dialog.contextmenu(['Retrieve Only', 'Keep locally', 'WAF Play', 'Reset Add-on', 'Full NFO refresh', 'Cancel'])

        if retr == -1 or retr == 5:
            return
        
        if retr == 4:
            base_url = get_base_urlCT(addon)
            # full nfo refreshcall
            if fetch_jg_infoCT(base_url, "/trigger_full_nfo_refresh", get_base_ident_paramsCT(addon), None):
                jgnotifCT("Full NFO Refresh", "Triggered", True)


        if retr == 3:
            #xbmc.log(f"{LOG} User requested addon reset", xbmc.LOGINFO)
            deleteUidFile(addon)
            setConfigToDefaults(addon)
            jgnotifCT("Add-on config", "Reinitialized", True)
            askUserRestartCT("UID file deleted")

            return

        if retr == 0 or retr == 1 or retr == 2:

            '''
            pbar = xbmcgui.DialogProgressBG()
            pbar.create("My Addon", "Preparing…")

            for i in range(101):
                pbar.update(i, message=f"Progress: {i}%")
                time.sleep(0.05)

            pbar.close()
            '''
            
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
