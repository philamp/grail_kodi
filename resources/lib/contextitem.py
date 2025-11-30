# contextitem.py
import xbmcaddon
import sys
import xbmc
import xbmcgui

def safe_get(index, default=None):
    try:
        return sys.argv[index]
    except Exception:
        return default

def run():
    LOG = "[GrailContext]"
    addon = xbmcaddon.Addon()
    xbmcgui.Dialog().notification(
        "Kodi Grail",
        "}{ Actions clicked",
        icon=addon.getAddonInfo("icon"),
        time=3000
    )
    try:
        action = safe_get(1, "unknown")
        media_path = safe_get(2, "none")

        xbmc.log(f"{LOG} called: action={action}, path={media_path}", xbmc.LOGINFO)

        #dialog = xbmcgui.Dialog()
        #retr = dialog.contextmenu(['Option #1', 'Option #2', 'Option #3'])

        title = xbmc.getInfoLabel("ListItem.Title") or "Inconnu"
        dbid = xbmc.getInfoLabel("ListItem.DBID") or "N/A"
        dbtype = xbmc.getInfoLabel("ListItem.DBTYPE") or "?"

        message = (
            f"Action : {action}\n\n"
            f"clicked: dfdsf\n\n"
            f"ID : {dbid}\n"
            f"Titre : {title}\n"
            f"Type : {dbtype}\n"
            f"Chemin : {media_path}"
        )

        xbmcgui.Dialog().ok("Kodi Grail", message)

    except Exception as e:
        xbmc.log(f"{LOG} ERROR: {e}", xbmc.LOGERROR)
        try:
            xbmcgui.Dialog().notification("Kodi Grail", f"Erreur : {e}", xbmcgui.NOTIFICATION_ERROR, 4000)
        except Exception:
            pass


if __name__ == "__main__":
    xbmc.log("[context.kodi_grail] contextitem run()", xbmc.LOGINFO)
    run()
