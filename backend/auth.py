import logging
from ldap3 import ALL, Connection, Server


logger = logging.getLogger("bwiki.auth")


def check_ldap_login(username: str, password: str) -> bool:
    """Prueft Benutzername/Passwort gegen den LDAP-Server."""
    # LDAP-Serverobjekt aufbauen; get_info=ALL liest Schema/Serverinfos mit ein.
    server = Server("ldap://12353-DC01.bwi.local", get_info=ALL)
    # Benutzer wird ueber UPN angemeldet (user@domain).
    user_dn = f"{username}@bwi.local"

    try:
        # auto_bind=True fuehrt den Login direkt beim Erstellen der Connection aus.
        conn = Connection(server, user=user_dn, password=password, auto_bind=True)

        logger.info(f"✅ Login ERFOLGREICH für User: {username}")
        conn.unbind()
        return True

    except Exception as e:
        # Jeder Bind-Fehler (falsches Passwort, Netzwerk, LDAP down, ...) landet hier.
        logger.warning(f"❌ Login FEHLGESCHLAGEN für {username}. Grund: {e}")
        return False