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

        title = xbmc.getInfoLabel("ListItem.Title") or "NOTITLE"
        dbid = xbmc.getInfoLabel("ListItem.DBID") or "NOID"
        dbtype = xbmc.getInfoLabel("ListItem.DBTYPE") or "NOVIDEOTYPE"

        base_url = get_base_urlCT(addon)

        preflang = "preferred language"

        if receivedData := fetch_jg_infoCT(base_url, f"/get_cmenu_for/{dbtype}/{dbid}", get_base_ident_paramsCT(addon), None):
            selectable = []
            menu = []
            for _, (key, val) in enumerate(receivedData['menu'].items()):
                selectable.append(val)
                menu.append(key)
            
            preflang = receivedData.get('preflang', preflang)

        else:
            menu = ["JG server response error"]





        #action = safe_get(1, "unknown")
        #media_path = safe_get(2, "none")

        #xbmc.log(f"{LOG} called: action={action}, path={media_path}", xbmc.LOGINFO)

        dialog = xbmcgui.Dialog()
        resp = dialog.contextmenu(menu)


        if resp == -1 or resp >= len(selectable) or resp == 1:
            return


        #'Trigger full scan': '#FULLSCAN',
        #'Reset Add-on': '#RESETADDON',
        #'Open Add-on settings': '#OPENSETTINGS'

        if selectable[resp] == '#KEEPLOCAL' or selectable[resp] == '#KEEPLOCALUHD':
            Ltpl = ""
            Qtpl = ""

            Lpolicy = 1
            if confirmPopinCT("Preferred audio needed ?", f"Do you also want to keep the {preflang} AUDIO version of this movie (if found) ?"):
                Lpolicy = 2
                Ltpl = ' with pref audio'
            
            
            Qpolicy = 1
            if selectable[resp] == '#KEEPLOCALUHD':
                Qpolicy = 2
                Qtpl = ' in UHD'


            payload = {
                'Qpolicy': Qpolicy,
                'Lpolicy': Lpolicy,
                'parentPaths': receivedData['payload']
            }

            if fetch_jg_infoCT(base_url, '/set_policy', get_base_ident_paramsCT(addon), None, timeout=10, json_data=payload):
                jgnotifCT(f"Keeping {dbtype}|", f"{title}{Qtpl}{Ltpl}", True)                

            return



        if selectable[resp] == '#SUBMENU':
            selectable = []
            menu = []
            for i, (key, val) in enumerate(receivedData['submenu'].items()):
                selectable.append(val)
                menu.append(key)
            dialog = xbmcgui.Dialog()
            resp = dialog.contextmenu(menu)



            if selectable[resp] == '#FULLNFOREFRESH':
                if confirmPopinCT("Full NFO Refresh", "Are you sure you want to trigger a full NFO refresh? This may take a while. Please wait for the batch to be generated on server side"):
                    base_url = get_base_urlCT(addon)
                    # full nfo refreshcall
                    if fetch_jg_infoCT(base_url, "/trigger_full_nfo_refresh", get_base_ident_paramsCT(addon), None):
                        jgnotifCT("Full NFO Refresh", "Triggered", True)
                        
                        xbmc.executebuiltin('ActivateWindow(Settings)')
                        xbmc.sleep(2000)
                        jgnotifCT("Full NFO Refresh", "Please wait for the server to respond", True)
                return
            
            if selectable[resp] == '#DELTANFOREFRESH':
                if confirmPopinCT("Delta NFO Refresh", "Are you sure you want to trigger a delta NFO refresh? This may take a while. Please wait for the batch to be generated on server side"):
                    base_url = get_base_urlCT(addon)
                    # full nfo refreshcall
                    if fetch_jg_infoCT(base_url, "/trigger_full_nfo_refresh", get_base_ident_paramsCT(addon), "&deltamode=y"):
                        jgnotifCT("Delta NFO Refresh", "Triggered", True)
                        
                        xbmc.executebuiltin('ActivateWindow(Settings)')
                        xbmc.sleep(2000)
                        jgnotifCT("Delta NFO Refresh", "Please wait for the server to respond", True)
                return


            if selectable[resp] == '#FULLSCAN':
                if confirmPopinCT("Full Scan", "Are you sure you want to trigger a full library scan? This may take a while."):
                    base_url = get_base_urlCT(addon)
                    # full scan call
                    if fetch_jg_infoCT(base_url, "/ask_kodi_refresh", get_base_ident_paramsCT(addon), None):
                        jgnotifCT("Full Scan", "Triggered", True)
                return


            if selectable[resp] == '#OPENSETTINGS':
                addon.openSettings()
                return
            
            if selectable[resp] == '#RESETADDON':
                if confirmPopinCT("Reset Add-on", "Are you sure you want to reset the add-on configuration? This will delete your UID file and set all settings to default. You will need to restart Kodi."):
                    deleteUidFile(addon)
                    setConfigToDefaults(addon)
                    jgnotifCT("Add-on config", "Reinitialized", True)
                    askUserRestartCT("Add-on reset")
                return
        


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
