import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon
import os
import shutil
import socket
import struct
import select
import threading
import time
import zipfile
import urllib.request
import uuid
import json

VERSION="20250808"

def get_installation_uid(addon):
    install_path = xbmcvfs.translatePath(addon.getAddonInfo("path"))
    uid_file = os.path.join(install_path, "addon_uuid.txt")

    if xbmcvfs.exists(uid_file):
        with xbmcvfs.File(uid_file) as f:
            return f.read().strip()

    unique_id = str(uuid.uuid4())
    with xbmcvfs.File(uid_file, "w") as f:
        f.write(unique_id)

    return unique_id

def patch_advancedsettings_mysql(host, user, password, dbnameprefix, port):
    adv_path = xbmcvfs.translatePath("special://profile/advancedsettings.xml")

    xml_block = f"""<videodatabase>
    <type>mysql</type>
    <host>{host}</host>
    <port>{port}</port>
    <user>{user}</user>
    <pass>{password}</pass>
    <name>{dbnameprefix}</name>
</videodatabase>"""

    if xbmcvfs.exists(adv_path):
        with xbmcvfs.File(adv_path) as f:
            content = f.read()
        import re
        # Supprimer toute ancienne section videodatabase
        content_cleaned = re.sub(r"<videodatabase>.*?</videodatabase>", "", content, flags=re.DOTALL)
        # Supprimer les retours à la ligne avant </advancedsettings>
        content_cleaned = re.sub(r"\n*\s*</advancedsettings>", "</advancedsettings>", content_cleaned)
        # Injecter proprement juste avant la balise fermante
        new_content = content_cleaned.replace("</advancedsettings>", xml_block + "</advancedsettings>")
    else:
        content = ""
        new_content = f"<advancedsettings>{xml_block}</advancedsettings>"


    # Si le contenu n'a pas changé, ne rien faire
    if new_content.strip() == content.strip():
        xbmc.log(f"[context.kodi_grail] NO change in adv settings:", xbmc.LOGINFO)
        return False

    xbmc.log(f"[context.kodi_grail] CHANGES in adv settings:", xbmc.LOGINFO)
    # Sinon, écrire le nouveau contenu
    with xbmcvfs.File(adv_path, "w") as f:

        f.write(new_content)
    return True

def kodi_version():
    build = xbmc.getInfoLabel("System.BuildVersion")
    kodi_major = int(build.split('.')[0]) if build else 0
    xbmc.log(f"[context.kodi_grail] Version Kodi détectée : {build}", xbmc.LOGINFO)
    return kodi_major


def select_mysql_db(dbs, puid):
    if not dbs:
        return None
    dialog = xbmcgui.Dialog()

    

    index = dialog.select("Choisir une base MySQL", dbs)
    if index >= 0:
        return dbs[index]
    return None

def fetch_mysql_dbs(url):
    try:
        xbmc.log(f"[context.kodi_grail] Requête JellyGrail : {url}", xbmc.LOGINFO)
        with urllib.request.urlopen(url, timeout=5) as response:
            data = response.read().decode("utf-8")
        result = json.loads(data)
        #result = {"databases": ["movies_db", "tvshows_db", "music_db"]}  # Simulé pour l'exemple
        
        return [entry.get("dbname") for uid, entry in result.items()]


    except Exception as e:
        xbmc.log(f"[context.kodi_grail] Erreur JellyGrail fetch : {e}", xbmc.LOGERROR)
        return []

def install_addon_from_local_zip(zip_path):
    addons_dir = xbmcvfs.translatePath("special://home/addons/")
    xbmc.log(f"[context.kodi_grail] Installation manuelle depuis {zip_path}", xbmc.LOGINFO)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            root_name = zip_ref.namelist()[0].split('/')[0]
            dest_path = os.path.join(addons_dir, root_name)

            # Supprimer ancienne version
            if xbmcvfs.exists(dest_path):
                xbmc.log(f"[context.kodi_grail] Suppression de l'ancienne version : {dest_path}", xbmc.LOGINFO)
                xbmcvfs.rmdir(dest_path, force=True)

            # Extraction
            zip_ref.extractall(addons_dir)
            xbmc.log(f"[context.kodi_grail] Extraction réussie vers {addons_dir}", xbmc.LOGINFO)

        # Forcer un reload des addons
        xbmc.executebuiltin("UpdateLocalAddons")
        xbmc.executebuiltin("UpdateAddonRepos")

        xbmcgui.Dialog().notification("Kodi Grail", f"Addon installé : {root_name}", time=4000)
    except Exception as e:
        xbmc.log(f"[context.kodi_grail] Manual install error : {e}", xbmc.LOGERROR)

def install_addon_from_dav(dav_url):
    try:
        temp_path = xbmcvfs.translatePath("special://home/cache/")
        zip_name = dav_url.split('/')[-1]
        local_path = temp_path + zip_name

        xbmc.log(f"[context.kodi_grail] Téléchargement depuis {dav_url} vers {local_path}", xbmc.LOGINFO)

        if xbmcvfs.copy(dav_url, local_path):
            xbmc.log(f"[context.kodi_grail] Copie réussie: {local_path}", xbmc.LOGINFO)
            install_addon_from_local_zip(local_path)
            # xbmc.executebuiltin(f'InstallAddonFromZip("{local_path}")')

            xbmcgui.Dialog().ok("Kodi Grail", "Restart Kodi to complete JellyGrail addon installation")

        else:
            xbmc.log(f"[context.kodi_grail] Copy failed from {dav_url}", xbmc.LOGERROR)

    except Exception as e:
        xbmc.log(f"[context.kodi_grail] Installation Errot: {e}", xbmc.LOGERROR)

# ==============================
#  Préchargement du menu contextuel
# ==============================
def preload_context():
    """Précharge le module contextuel pour initialiser Kodi (évite le crash SIGSEGV)."""
    try:
        import resources.lib.contextitem as contextitem
        xbmc.log("[context.kodi_grail] contextitem preloaded successfully", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[context.kodi_grail] preload failed: {e}", xbmc.LOGERROR)


# ==============================
#  Gestion du multicast (universelle)
# ==============================
def join_multicast(sock, mcast_addr="239.255.255.250"):
    """Joint le groupe multicast, compatible Android, webOS, CoreELEC, etc."""
    try:
        # Détection de l'adresse IP locale active (pour Android notamment)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        iface_ip = s.getsockname()[0]
        s.close()
    except Exception:
        iface_ip = "0.0.0.0"

    try:
        mreq = struct.pack("4s4s",
                           socket.inet_aton(mcast_addr),
                           socket.inet_aton(iface_ip))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        xbmc.log(f"[context.kodi_grail] joined multicast group {mcast_addr} on {iface_ip}", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[context.kodi_grail] multicast join failed: {e}", xbmc.LOGERROR)


# ==============================
#  Écoute SSDP (avec durée limitée)
# ==============================
def listen_ssdp(monitor, port=6505, mcast_addr="239.255.255.250", duration=20):
    
    """
    Écoute les messages SSDP multicast sur le port spécifié pendant `duration` secondes.
    duration=0  => écoute indéfiniment (ou jusqu'à arrêt Kodi).
    """

    kodiverison = kodi_version()

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            sock.bind(('', port))
        except OSError as e:
            xbmc.log(f"[context.kodi_grail] bind({port}) failed: {e}", xbmc.LOGERROR)
            return

        # Joindre le groupe multicast
        join_multicast(sock, mcast_addr)

        sock.setblocking(False)
        xbmc.log(f"[context.kodi_grail] SSDP listener started on {mcast_addr}:{port}, duration={duration}s", xbmc.LOGINFO)

        #monitor = xbmc.Monitor()
        end_time = None if duration == 0 else (time.time() + float(duration))

        while True:
            # Arrêt si Kodi s'arrête
            if monitor.abortRequested():
                xbmc.log("[context.kodi_grail] SSDP listener stopping because Kodi requested abort", xbmc.LOGINFO)
                break
            # Arrêt si durée écoulée (si duration > 0)
            if end_time is not None and time.time() >= end_time:
                xbmc.log("[context.kodi_grail] SSDP listener duration expired", xbmc.LOGINFO)
                xbmcgui.Dialog().notification(
                    "KodiGrail| S2: SSDP",
                    "FAILED (20s max) :(",
                    xbmcgui.NOTIFICATION_INFO,
                    1500
                )
                break

            # attente non bloquante
            readable, _, _ = select.select([sock], [], [], 1.0)
            if sock in readable:
                try:
                    data, addr = sock.recvfrom(65535)
                    msg = data.decode(errors="ignore").strip()
                    xbmc.log(f"[context.kodi_grail] SSDP from {addr}: {msg}", xbmc.LOGINFO)
                    msga = msg.split("|")

                    if len(msg) and msga[0] == "JGx":
                        if msga[1] != VERSION:
                            xbmcgui.Dialog().notification(
                                "KodiGrail| S2: SSDP",
                                f"Step 2 - SSDP received: Server version: {msga[1]} different from addon version {VERSION}",
                                xbmcgui.NOTIFICATION_INFO,
                                1500
                            )
                            # since we know server ip we can download the updated addon
                            dav_url = f"dav://{addr[0]}:{msga[5]}/actual/kodi/software/context.kodigrail.{VERSION}.zip"
                            install_addon_from_dav(dav_url)

                        else:
                            xbmcgui.Dialog().notification(
                                "KodiGrail| S2: SSDP",
                                f"Add-on V.{msga[1]} is server compatible :)",
                                xbmcgui.NOTIFICATION_INFO,
                                1500
                            )

                            # --- SSDP to official kodi settings storage ---

                            if monitor.addon.getSettingString("jgip") != addr[0] or monitor.addon.getSettingInt("jgport") != int(msga[3]):
                                xbmcgui.Dialog().notification(
                                    "KodiGrail| S3: Base settings",
                                    f"Updating settings...",
                                    xbmcgui.NOTIFICATION_INFO,
                                    1500
                                )
                                

                                monitor.set_silent() #to avoid loop

                                xbmc.sleep(500) # let settings be saved

                                # ---1 Store the 2 main things
                                # 1 - JGIP
                                if monitor.addon.getSettingString("jgip") != addr[0]:
                                    monitor.addon.setSetting("jgip", addr[0])
                                    xbmc.log("[context.kodi_grail]jgip:", xbmc.LOGINFO)

                                # 2 - JGPORT
                                if monitor.addon.getSettingInt("jgport") != int(msga[3]):
                                    monitor.addon.setSetting("jgport", msga[3])
                                    xbmc.log("[context.kodi_grail]jgport:", xbmc.LOGINFO)

                                xbmc.sleep(500)

                                monitor.set_not_silent()

                            else:
                                xbmcgui.Dialog().notification(
                                    "KodiGrail| S3: Base settings",
                                    f"No change in basic settings",
                                    xbmcgui.NOTIFICATION_INFO,
                                    1500
                                )


                            # --- SSDP to storage END ---
                            


                            

                            # we get the rest via WS and we give the token given by SSDP
                            # we have the port for SQL in SSDP -> advsettings

                            # WS design is:
                            # - POST to /kodi_login with add-on instance UUDID
                            uuid = get_installation_uid(monitor.addon)
                            # - and token from SSDP 
                            ssdp_token = msga[6]
                            # - and KODI version
                            kodiverison = kodi_version()

                            xbmc.log(f"[context.kodi_grail] UUID:{uuid}, SSDP_TOKEN: {ssdp_token}, kodiverison: {kodiverison}", xbmc.LOGINFO)
                            
                            # - JG responds with a list(S) of possible databases + new db (or just one if it recognizes the UUID)
                            # - so the seed is always given by JG
                            # - (we select one if many) and store it in advsettings.xml




                            # - when storing in advanced settings, we check for changes, if changes, we ask for a restart of Kodi
                            # host, user, password, dbnameprefix, port):
                            # this is a POC
                            if patch_advancedsettings_mysql(addr[0], "kodi", "kodi", "kodi_video", msga[4]):
                                askUserRestart("(userdata/advancedsettings.xml updated)")

                            

                            dbs = fetch_mysql_dbs(f"http://{addr[0]}:{msga[3]}/get_compatible_kodiDBs?kodi_version={kodiverison}&uid={uuid}")
                            if not dbs:
                                xbmcgui.Dialog().ok("Kodi Grail", "Aucune base MySQL trouvée.")
                                return

                            selected = select_mysql_db(dbs, uuid)
                            if selected:
                                xbmcgui.Dialog().ok("Kodi Grail", f"Base sélectionnée : [B]{selected}[/B]")
                                xbmc.log(f"[context.kodi_grail] Base MySQL sélectionnée : {selected}", xbmc.LOGINFO)

                    else:
                        
                        
                        xbmcgui.Dialog().notification(
                            "KodiGrail| S2: SSDP",
                            f"Failed, you have to manually configure the add-on",
                            xbmcgui.NOTIFICATION_INFO,
                            1500
                        )
                        

                    if addr[0] != msga[2]:
                        xbmc.log(f"[context.kodi_grail] Warning: IP mismatch between UDP source {addr[0]} and message {msga[2]}", xbmc.LOGWARNING)
                        xbmcgui.Dialog().notification(
                            "KodiGrail| S2: SSDP",
                            f"IP mismatch between SSDP and JellyGrail message: {addr[0]} != {msga[2]}",
                                xbmcgui.NOTIFICATION_INFO,
                                1500
                            )

                    break
                except Exception as e:
                    xbmc.log(f"[context.kodi_grail] SSDP recv error: {e}", xbmc.LOGERROR)
                    xbmcgui.Dialog().notification(
                        "KodiGrail| S2: SSDP",
                        f"SSDP Failure when getting or storing message :(",
                        xbmcgui.NOTIFICATION_INFO,
                        1500
                    )
                    break

    except Exception as e:
        xbmc.log(f"[context.kodi_grail] SSDP listener setup failed: {e}", xbmc.LOGERROR)
    finally:
        try:
            sock.close()
        except Exception:
            pass
        xbmc.log("[context.kodi_grail] SSDP listener stopped", xbmc.LOGINFO)


def askUserRestart(addedMsg=""):
    xbmcgui.Dialog().ok("Kodi Grail", f"Please restart Kodi to apply new settings {addedMsg}")

class GrailMonitor(xbmc.Monitor):



    def __init__(self, addon):
        super().__init__()
        self.addon = addon
        self._ignore_changes = False

    def set_silent(self):
        self._ignore_changes = True

    def set_not_silent(self):
        self._ignore_changes = False


    def onSettingsChanged(self):

        if self._ignore_changes:
            xbmc.log("[context.kodi_grail] above var silently set", xbmc.LOGINFO)
            return
        
        # if not silently set = if set in config
        askUserRestart()

# ==============================
#  Point d'entrée principal
# ==============================
if __name__ == "__main__":
    preload_context()
    addon = xbmcaddon.Addon(id="context.kodi_grail")
    monitor = GrailMonitor(addon)

    xbmcgui.Dialog().notification(
        "KodiGrail| S1: Loading",
        "Success",
        xbmcgui.NOTIFICATION_INFO,
        1500
    )
    if addon.getSettingBool("override_ssdp_settings"):
        xbmcgui.Dialog().notification(
            "KodiGrail| S2: SSDP ignored",
            f"Manual settings used",
            xbmcgui.NOTIFICATION_INFO,
            1500
        )
    else:
        thread = threading.Thread(target=listen_ssdp, kwargs={'monitor': monitor, 'port': 6505, 'mcast_addr': "239.255.255.250", 'duration': 20}, daemon=True)
        thread.start()

    #xbmc.log("[context.kodi_grail] init_context service started", xbmc.LOGINFO)

    # On attend la fin du service ou l'arrêt Kodi (la boucle principale reste utile si tu veux garder le service vivant)

    while not monitor.abortRequested():
        # oportunity to make periodic tasks if needed
        if monitor.waitForAbort(5):
            # Abort was requested while waiting. We should exit
            break

    #while not monitor.waitForAbort(0.5):
    #    pass

    #while not monitor.abortRequested():
    #    xbmc.sleep(500)

'''
def install_addon_from_dav(dav_url, local_filename=None):
    """
    Télécharge un fichier ZIP d'addon depuis une URL WebDAV et l'installe dans Kodi.
    Exemple : dav_url = "dav://user:pass@192.168.0.10/addons/plugin.video.foo.zip"
    """

    try:
        # Si pas de nom local précisé, extraire le nom depuis l’URL
        if not local_filename:
            local_filename = os.path.basename(dav_url)

        # Emplacement temporaire (le cache Kodi est accessible en écriture)
        temp_dir = xbmcvfs.translatePath("special://home/cache/")
        local_path = os.path.join(temp_dir, local_filename)

        xbmc.log(f"[context.kodi_grail] Téléchargement depuis {dav_url} vers {local_path}", xbmc.LOGINFO)

        # Lecture via xbmcvfs (Kodi gère WebDAV)
        src_file = xbmcvfs.File(dav_url, 'rb')
        dest_file = xbmcvfs.File(local_path, 'wb')

        buffer_size = 1024 * 1024  # 1 Mo
        while True:
            data = src_file.read(buffer_size)
            if not data:
                break
            dest_file.write(data)

        src_file.close()
        dest_file.close()

        xbmc.log(f"[context.kodi_grail] Téléchargement terminé : {local_path}", xbmc.LOGINFO)

        # Installation de l'addon depuis le ZIP téléchargé
        xbmc.log(f"[context.kodi_grail] Installation de {local_path}", xbmc.LOGINFO)
        xbmc.executebuiltin(f'InstallAddonFromZip("{local_path}")')

        xbmcgui.Dialog().notification("Kodi Grail", f"Addon installé depuis {dav_url}", time=4000)
        return True

    except Exception as e:
        xbmc.log(f"[context.kodi_grail] Erreur lors du téléchargement/installation: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Kodi Grail", f"Erreur: {e}", time=5000)
        return False
'''

'''
def install_addon_from_http(url):
    temp_path = xbmc.translatePath("special://home/cache/")
    local_zip = os.path.join(temp_path, os.path.basename(url))

    xbmc.log(f"[context.kodi_grail] Téléchargement direct HTTP depuis {url}", xbmc.LOGINFO)

    try:
        urllib.request.urlretrieve(url, local_zip)
        xbmc.log(f"[context.kodi_grail] Téléchargement terminé : {local_zip}", xbmc.LOGINFO)
        xbmc.executebuiltin(f'InstallAddonFromZip("{local_zip}")')
    except Exception as e:
        xbmc.log(f"[context.kodi_grail] Erreur téléchargement HTTP : {e}", xbmc.LOGERROR)
'''