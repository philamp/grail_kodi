import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon
import os

VERSION="20250808"

def askUserRestartCT(addedMsg=""):
    xbmcgui.Dialog().ok("JellyGrail| Restart needed", f"Please restart Kodi - {addedMsg}")