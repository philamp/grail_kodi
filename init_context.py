import xbmc
import xbmcgui
import socket
import struct
import select
import threading
import time


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
def listen_ssdp(port=6505, mcast_addr="239.255.255.250", duration=20):
    VERSION="20250808"
    """
    Écoute les messages SSDP multicast sur le port spécifié pendant `duration` secondes.
    duration=0  => écoute indéfiniment (ou jusqu'à arrêt Kodi).
    """
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

        monitor = xbmc.Monitor()
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
                    "JellyGrail Kodi",
                    "Step 2 - SSDP FAILED (20s max) :("
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
                    if msga[0] != VERSION:
                        xbmcgui.Dialog().notification(
                            "JellyGrail Kodi",
                            f"Step 2 - SSDP received: Server version: {msga[0]} different from addon version {VERSION}"
                        )
                        
                    xbmcgui.Dialog().notification(
                        "JellyGrail Kodi",
                        f"Step 2 - SSDP received: {msga[0]}"
                    )
                    break
                except Exception as e:
                    xbmc.log(f"[context.kodi_grail] SSDP recv error: {e}", xbmc.LOGERROR)

    except Exception as e:
        xbmc.log(f"[context.kodi_grail] SSDP listener setup failed: {e}", xbmc.LOGERROR)
    finally:
        try:
            sock.close()
        except Exception:
            pass
        xbmc.log("[context.kodi_grail] SSDP listener stopped", xbmc.LOGINFO)


# ==============================
#  Point d'entrée principal
# ==============================
if __name__ == "__main__":
    preload_context()
    
    xbmcgui.Dialog().notification(
        "JellyGrail Kodi",
        "Step 1 - Loading : Success"
    )

    # Lancer l’écoute SSDP dans un thread séparé pour 20 secondes
    thread = threading.Thread(target=listen_ssdp, kwargs={'port': 6505, 'mcast_addr': "239.255.255.250", 'duration': 20}, daemon=True)
    thread.start()

    xbmc.log("[context.kodi_grail] init_context service started", xbmc.LOGINFO)

    # On attend la fin du service ou l'arrêt Kodi (la boucle principale reste utile si tu veux garder le service vivant)
    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        xbmc.sleep(500)
