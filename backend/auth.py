import logging
from ldap3 import Server, Connection, ALL


logger = logging.getLogger("bwiki.auth")

def check_ldap_login(username: str, password: str) -> bool:
  
    server = Server('ldap://12353-DC01.bwi.local', get_info=ALL)
    
    
    user_dn = f"{username}@bwi.local" 
    
    try:
        
        conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        
        logger.info(f"✅ Login ERFOLGREICH für User: {username}")
        conn.unbind()
        return True
        
    except Exception as e:
        logger.warning(f"❌ Login FEHLGESCHLAGEN für {username}. Grund: {e}")
        return False