import xbmcgui
import xbmcaddon
import xbmc

def run():
    addon = xbmcaddon.Addon()
    xbmcgui.Dialog().notification(
        "Kodi Grail",
        "Play with Grail clicked!",
        icon=addon.getAddonInfo("icon"),
        time=3000
    )

if __name__ == "__main__":
    xbmc.log("[context.kodi_grail] contextitem run()", xbmc.LOGINFO)
    run()
