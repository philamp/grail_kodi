import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon
import os
#import shutil
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

dbVerified = None
restartAsked = False
viaProxy = False
anyRefreshWorking = False

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


def patch_sources_webdav(ipport, roots = ["movies", "shows"]):
    adv_path = xbmcvfs.translatePath("special://profile/sources.xml")

    '''
    xml_block = f"""<video>
    <default pathversion="1"></default>
    <source>
        <name>JG-Movies</name>
        <path pathversion="1">dav://{ipport}/virtual/movies/</path>
        <allowsharing>true</allowsharing>
    </source>
    <source>
        <name>JG-Shows</name>
        <path pathversion="1">dav://{ipport}/virtual/shows/</path>
        <allowsharing>true</allowsharing>
    </source>
    </video>"""
    '''
    
    xml_block = f"""<video>
    <default pathversion="1"></default>"""

    for root in roots:
        xml_block += f"""<source>
            <name>JG-{root}</name>
            <path pathversion="1">dav://{ipport}/virtual/{root}/</path>
            <allowsharing>true</allowsharing>
        </source>"""

    xml_block += f"""</video>"""

    if xbmcvfs.exists(adv_path):
        with xbmcvfs.File(adv_path) as f:
            content = f.read()
        import re
        # Supprimer toute ancienne section video
        content_cleaned = re.sub(r"<video>.*?</video>", "", content, flags=re.DOTALL)
        # Supprimer les retours à la ligne avant </sources>
        content_cleaned = re.sub(r"\n*\s*</sources>", "</sources>", content_cleaned)
        # Injecter proprement juste avant la balise fermante
        new_content = content_cleaned.replace("</sources>", xml_block + "</sources>")
    else:
        content = ""
        new_content = f"<sources>{xml_block}</sources>"


    # Si le contenu n'a pas changé, ne rien faire
    if new_content.strip() == content.strip():
        xbmc.log(f"[context.kodi_grail] NO change in sources settings:", xbmc.LOGINFO)
        return False

    xbmc.log(f"[context.kodi_grail] CHANGES in sources settings:", xbmc.LOGINFO)
    # Sinon, écrire le nouveau contenu
    with xbmcvfs.File(adv_path, "w") as f:

        f.write(new_content)
    return True

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
    return kodi_major

def select_mysql_db(monitor, dbs):
    if not dbs:
        return None
    dialog = xbmcgui.Dialog()

    dbs_label = [val.get("db_created_date") for _, val in dbs.items()]
    dbs_name = [val.get("dbname") for _, val in dbs.items()]

    if len(dbs_name) < 2:
        if dbs_label[0] == "New DB":
            xbmcgui.Dialog().ok("JellyGrail", f"New Database")
        else:
            monitor.jgnotif("Mysql| Will use DB:", f"{dbs_label[0]}", False)

        return dbs_name[0]

    index = dialog.select("Choose DB among existing ones:", dbs_label)
    if index >= 0:
        return dbs_name[index]

    return None

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

        xbmcgui.Dialog().notification("JellyGrail", f"Addon installé : {root_name}", time=4000)
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

            xbmcgui.Dialog().ok("JellyGrail", "Restart Kodi to complete JellyGrail addon installation")

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


def guess_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        iface_ip = s.getsockname()[0]
    except Exception:
        iface_ip = "0.0.0.0"
    finally:
        s.close()
    return iface_ip

# ==============================
#  Gestion du multicast (universelle)
# ==============================
def join_multicast(sock, mcast_addr="239.255.255.250"):

    iface_ip = guess_ip()

    try:
        if iface_ip != "0.0.0.0":
            mreq = struct.pack("4s4s",
                            socket.inet_aton(mcast_addr),
                            socket.inet_aton(iface_ip))
        else:
            mreq = struct.pack("4sl",
                           socket.inet_aton(mcast_addr),
                           socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        xbmc.log(f"[context.kodi_grail] joined multicast group {mcast_addr} on {iface_ip}", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[context.kodi_grail] multicast join failed: {e}", xbmc.LOGERROR)


def push_jg_info(monitor, base_url, path, params, optionalparams):

    global dbVerified

    if not optionalparams:
        return False
    
    result = fetch_jg_info(monitor, base_url, path, params, optionalparams)

    if result.get("status") == 200:
        dbVerified = None
        return True
    
    elif result.get("status") == 201:
        return True
    
    return False



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
            xbmc.log("[context.kodi_grail] Unauthorized (401)", xbmc.LOGWARNING)
            monitor.jgnotif("WS| Auth error", f"{path}", True)
            return None
        else:
            xbmc.log(f"[context.kodi_grail] Fetch failed {path}: {e.code}: {e.reason}", xbmc.LOGERROR)
            return None
        
    except Exception as e:
        xbmc.log(f"[context.kodi_grail] Fetch failed {path}: {e}", xbmc.LOGERROR)
        return None

def get_base_ident_params(monitor, jgtoken):

    return f"?token={jgtoken}&kodi_version={kodi_version()}&uid={monitor.get_uid()}&ip={monitor.get_ip()}"

def fetch_push_patch(monitor, via_proxy = False):

    global dbVerified
    global viaProxy

    jgip = monitor.addon.getSettingString("jgip")
    jgport = monitor.addon.getSettingInt("jgport")
    jgtoken = monitor.addon.getSettingString("jgtoken")
    jgproxy = monitor.addon.getSettingString("jgproxy")

    if via_proxy:
        base_url = jgproxy + "/api"
        viaProxy = True
    else:
        base_url = f"http://{jgip}:{jgport}/api"

    askRestart = ""

    if jgpayload := fetch_jg_info(monitor, base_url, "/get_compatible_kodiDBs", get_base_ident_params(monitor, jgtoken), None):
        if dbs := jgpayload.get("avail_dbs"):
            if selected := select_mysql_db(monitor, dbs):
                dbVerified = selected
                if push_jg_info(monitor, base_url, "/set_db_for_this_kodi", get_base_ident_params(monitor, jgtoken), f"&choice={selected}"):
                    if jginfo := jgpayload.get("jginfo"):


                        if via_proxy:
                            if "https:" in jgproxy:
                                dav_url = f"{jgproxy.replace("https:", "davs:")}"
                            else:
                                dav_url = f"{jgproxy.replace("http:", "dav:")}"
                        else:
                            dav_url = f"{jgip}:{jginfo.get("davport")}"

                        if patch_advancedsettings_mysql(jgip, jginfo.get("user"), jginfo.get("pwd"), selected, jginfo.get("port")):
                            askRestart += "(SQL settings changed)"
                        if patch_sources_webdav(dav_url):
                            askRestart += "(DAV settings changed)"
                        if askRestart != "":
                            askUserRestart(askRestart)
                            monitor.jgnotif("Config change", "Will be applied after restart", True)
                        else:
                            monitor.jgnotif("No Config change", "No restart needed", False)
                            monitor.jgnotif("Real-Debrid|", f"{jginfo.get("pdays")} remaining", True)
                        
                        return True
    
    return False


def triggerScan(monitor):

    global anyRefreshWorking

    if not anyRefreshWorking:
        anyRefreshWorking = True
        monitor.jgnotif("Scan|", "Triggered", False)
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"VideoLibrary.Scan","id":1}')
        
    else:
        monitor.jgnotif("Scan|", "ALREADY SCANNING", True) # should not happen

def askServerLoop(monitor):

    jgip = monitor.addon.getSettingString("jgip")
    jgport = monitor.addon.getSettingInt("jgport")
    jgtoken = monitor.addon.getSettingString("jgtoken")
    jgproxy = monitor.addon.getSettingString("jgproxy")

    if viaProxy:
        base_url = jgproxy + "/api"
    else:
        base_url = f"http://{jgip}:{jgport}/api"

    while not monitor.abortRequested() and dbVerified is not None:
        #break #TODO temp toremove
        xbmc.sleep(100)
        if anyRefreshWorking == False:
            if result := fetch_jg_info(monitor, base_url, "/what_should_do", get_base_ident_params(monitor, jgtoken), f"&db={dbVerified}", timeout=15):
                xbmc.log("[context.kodi_grail] entered result", xbmc.LOGINFO)

                if result.get("scan") == True:
                    xbmc.log("[context.kodi_grail] if scan true", xbmc.LOGINFO)


                    triggerScan(monitor)
                    #xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"VideoLibrary.Scan","id":1}')




                elif result.get("broken") == True:
                    xbmc.log("[context.kodi_grail] entered broken", xbmc.LOGINFO)
                    break
            else:
                monitor.jgnotif("Error|", "Critical: server broken", True)
                askUserRestart("Jellygrail Server broken, please restart it as well")
                break






def init(monitor):

    jgip = monitor.addon.getSettingString("jgip")
    jgport = monitor.addon.getSettingInt("jgport")
    jgtoken = monitor.addon.getSettingString("jgtoken")
    jgproxy = monitor.addon.getSettingString("jgproxy")

    success = False
    tries = 1

    config_set = jgip != "0.0.0.0" and jgport != 0 and jgtoken != "0"

    # -------

    while not success:

        if config_set or tries > 1:
            if fetch_push_patch(monitor, False):
                success = True
                break

        
        if jgproxy != "0" and tries == 1:  #Only once after the fail because SSDP wont need proxy

            if xbmcgui.Dialog().yesno(
                heading="JellyGrail Server Connection",
                message="Accessing the server via HTTP on Local network failed, Do you want to try the provided proxy fallback ?",
                nolabel="No",
                yeslabel="Yes"
            ):
                if fetch_push_patch(monitor, True):
                    success = True
                    break


        if not config_set:
            xbmcgui.Dialog().ok("JellyGrail", f"New installation, server discovery (during 10s max)")
        else:
            xbmcgui.Dialog().ok("JellyGrail", f"Existing installation, server re-discovery (during 10s max)")

        if not listen_ssdp(monitor):
            if not xbmcgui.Dialog().yesno(
                heading="JellyGrail Server Connection",
                message="Do you want to continue trying to connect to JellyGrail server or open manual settings ?",
                #line2="Continue discovering or stop and open config ?",
                nolabel="Open manual settings",
                yeslabel="Continue trying"
            ):
                break
    
        tries += 1
    
    # ------
    
    if success:
        monitor.jgnotif("Startup|", "Successful", False)
        return True
    else:
        monitor.jgnotif("Startup|", "Failed, opening config", True)
        return False

    # -----------

    # if VERSION mismatch ? TODO



# ==============================
#  Écoute SSDP (avec durée limitée)
# ==============================
def listen_ssdp(monitor, port=1900, mcast_addr="239.255.255.250", duration=10):
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            sock.bind(('', port))
        except OSError as e:
            monitor.jgnotif("SSDP| Error", f"bind({port}) failed", True, x = xbmc.LOGERROR, err = e)
            return

        # Joindre le groupe multicast
        join_multicast(sock, mcast_addr)

        sock.setblocking(False)
        monitor.jgnotif("SSDP| Started", f"multicast, port:{port}, {duration}s", False, x = xbmc.LOGINFO)

        #monitor = xbmc.Monitor()
        end_time = None if duration == 0 else (time.time() + float(duration))

        while True:
            # Arrêt si Kodi s'arrête
            if monitor.abortRequested():
                monitor.jgnotif("SSDP| Stopped", "Exit requested", False, x = xbmc.LOGINFO)
                break
            # Arrêt si durée écoulée (si duration > 0)
            if end_time is not None and time.time() >= end_time:
                
                monitor.jgnotif("SSDP| Stopped", f"Duration expired ({duration}s)", False, x = xbmc.LOGINFO)
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
                        if msga[1] != VERSION and 1 == 0: #TODO remove put elsewhere
                            monitor.jgnotif("SSDP|", f"Server version: {msga[1]} different from addon version {VERSION}", True)
                            # since we know server ip we can download the updated addon
                            '''
                            dav_url = f"dav://{addr[0]}:{msga[5]}/actual/kodi/software/context.kodigrail.{VERSION}.zip"
                            install_addon_from_dav(dav_url)
                            '''
                        else:

                            # --- SSDP to official kodi settings storage ---

                            if monitor.addon.getSettingString("jgip") != addr[0] or monitor.addon.getSettingInt("jgport") != int(msga[3]) or monitor.addon.getSettingString("jgtoken") != msga[6]:
                                monitor.jgnotif("SSDP|", "Updating server settings...", True)
                                

                                monitor.set_silent() #to avoid loop

                                xbmc.sleep(100) # let settings be saved

                                # ---1 Store the 2 main things
                                # 1 - JGIP
                                if monitor.addon.getSettingString("jgip") != addr[0]:
                                    monitor.addon.setSetting("jgip", addr[0])
                                # 2 - JGPORT
                                if monitor.addon.getSettingInt("jgport") != int(msga[3]):
                                    monitor.addon.setSetting("jgport", msga[3])
                                # 3 - JGPROXY
                                if monitor.addon.getSettingString("jgproxy") != msga[5]:
                                    monitor.addon.setSetting("jgproxy", msga[5])
                                # 4 - JGToken
                                if monitor.addon.getSettingString("jgtoken") != msga[6]:
                                    monitor.addon.setSetting("jgtoken", msga[6])

                                xbmc.sleep(100)

                                monitor.set_not_silent()

                                monitor.jgnotif("SSDP|", "...server settings updated", True)

                            else:
                                monitor.jgnotif("SSDP|", "...no change in server settings", False)

                            
                            # --- SSDP to storage END---
                            return True
                            


                            
                            '''
                            # we get the rest via WS and we give the token given by SSDP

                            # WSdesign is:
                            # - POST to /kodi_login with add-on instance UUDID
                            uuid = get_installation_uid(monitor.addon)
                            # - and token from SSDP 
                            ssdp_token = msga[6]
                            # - and KODIversion
                            kodiverison = kodi_version()

                            local_ip = guess_ip()

                            # we have the port for SQL in SSDP -> advsettings
                            xbmc.log(f"[context.kodi_grail] UUID:{uuid}, SSDP_TOKEN: {ssdp_token}, kodiverison: {kodiverison}", xbmc.LOGINFO)

                            BASE_URL = f"http://{addr[0]}:{msga[3]}/api"

                            BASE_IDENT = f"?token={ssdp_token}&kodi_version={kodiverison}&uid={uuid}&ip={local_ip}"
                            
                            ##uid##choice##ip##kodi_version
                            # - JG responds with a list(S) of possible databases + new db (or just one if it recognizes the UUID)
                            # - so the seed is always given by JG
                            # - (we select one if many) and store it in advsettings.xml

                            jginfo = fetch_mysql_info(f"{BASE_URL}/get_compatible_kodiDBs{BASE_IDENT}")
                            if not jginfo:
                                xbmcgui.Dialog().ok("JellyGrail", "No DB returned by the server.")
                                return
                            if dbs := jginfo.get("avail_dbs"):
                                selected = select_mysql_db(dbs)
                            if selected:
                                send_choice_to_server(f"{BASE_URL}/set_db_for_this_kodi{BASE_IDENT}&choice={selected}")
                                xbmc.log(f"[context.kodi_grail] Selected DB : {selected}", xbmc.LOGINFO)
                        
                            

                            if mysqlinfo := jginfo.get("jginfo"):
                            # - when storing in advanced settings, we check for c
                            # host, user, password, dbnameprefix, port):
                                # this is a POC
                                if patch_advancedsettings_mysql(addr[0], mysqlinfo.get("user"), mysqlinfo.get("pwd"), selected, mysqlinfo.get("port")):
                                    askUserRestart("(userdata/advancedsettings.xml updated)")
                            '''

                            



                    else:
                        monitor.jgnotif("SSDP|", "Failed, you have to manually configure the add-on", True, x = xbmc.LOGERROR)
                        

                    if addr[0] != msga[2]:
                        monitor.jgnotif("SSDP|", "Warning: IP mismatch between detected source and message", False, x = xbmc.LOGWARNING)

                    break
                except Exception as e:
                    xbmc.log(f"[context.kodi_grail] SSDP recv error: {e}", xbmc.LOGERROR)
                    break

        return False
    except Exception as e:
        xbmc.log(f"[context.kodi_grail] SSDP listener setup failed: {e}", xbmc.LOGERROR)
    finally:
        try:
            sock.close()
        except Exception:
            pass
        xbmc.log("[context.kodi_grail] SSDP listener stopped", xbmc.LOGINFO)


def askUserRestart(addedMsg=""):
    global restartAsked
    restartAsked = True
    xbmcgui.Dialog().ok("JellyGrail| Restart needed", f"Please restart Kodi - {addedMsg}")

class GrailMonitor(xbmc.Monitor):



    def __init__(self, addon):
        super().__init__()
        self.addon = addon
        self.ip = None
        self.uid = None
        self._ignore_changes = False
        self.debug_mode = self.addon.getSettingBool("debug_mode")

    def get_ip(self):
        if not self.ip:
            self.ip = guess_ip()
        return self.ip
    
    def get_uid(self):
        if not self.uid:
            self.uid = fetch_installation_uid(self.addon)
        return self.uid

    def jgnotif(self, h, p, force = False, x = xbmc.LOGINFO, err = ""):
        latency = 500 if self.debug_mode else 1500
        if self.debug_mode or force:
            xbmcgui.Dialog().notification("JellyGrail| "+h,p,xbmcgui.NOTIFICATION_INFO,latency)
        xbmc.log(f"{h}: {p}: {err}", x)

    def set_silent(self):
        self._ignore_changes = True

    def set_not_silent(self):
        self._ignore_changes = False

    def onNotification(self, sender, method, data):
        global anyRefreshWorking
        if method == "VideoLibrary.OnScanStarted":
            anyRefreshWorking = True
            self.jgnotif("Scan|", "STARTED", True)
            xbmc.log("[MyAddon] Scan started", xbmc.LOGINFO)

        if method == "VideoLibrary.OnScanFinished":
            anyRefreshWorking = False
            info = json.loads(data)
            self.jgnotif("Scan|", f"FINISHED", True)

            # Trigger your asyncio/event here
            # event.set()
        if method == "VideoLibrary.OnUpdate":
            self.jgnotif("Scan.NFOREFRESH", "NFOREFRESH", True)

    def onSettingsChanged(self):

        if self._ignore_changes:
            xbmc.log("[context.kodi_grail] above var silently set", xbmc.LOGINFO)
            return
        
        # if not silently set = if set in config
        self.debug_mode = self.addon.getSettingBool("debug_mode")
        askUserRestart()

# ==============================
#  Point d'entrée principal
# ==============================
if __name__ == "__main__":
    preload_context()
    addon = xbmcaddon.Addon(id="context.kodi_grail")
    monitor = GrailMonitor(addon)

    monitor.jgnotif("Loading|", "Detecting/Connecting JellyGrail server...", True)

    if not init(monitor):
        xbmcaddon.Addon().openSettings()
    else:
        if dbVerified and not restartAsked:
            monitor.jgnotif("Mysql|", "DB READY", True)

            askServerLoop(monitor)

        else:
            monitor.jgnotif("Mysql|", "PENDING RESTART", True)
            # long polling service....
            # what_should_i_do
            # -status
            # -action


    while not monitor.abortRequested():
        # oportunity to make periodic tasks if needed
        if monitor.waitForAbort(5):
            # Abort was requested while waiting. We should exit
            break

    '''
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
    '''

    #xbmc.log("[context.kodi_grail] init_context service started", xbmc.LOGINFO)

    # On attend la fin du service ou l'arrêt Kodi (la boucle principale reste utile si tu veux garder le service vivant)



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