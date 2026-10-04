import os
os.environ["OPENSSL_CONF"] = ""
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["SSL_ALLOW_UNSAFE_LEGACY_RENEGOTIATION"] = "1"

import subprocess
import sys

# ---------------------------------------------------------
# AJUSTE DE RUTAS (SOLUCIÓN A VS CODE Y PYDROID)
# ---------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RUTA_MPCRYPTO = os.path.join(SCRIPT_DIR, "recursos", "mpcrypto")

if RUTA_MPCRYPTO not in sys.path:
    sys.path.insert(0, RUTA_MPCRYPTO)

# Lista de paquetes de terceros (CORREGIDO pycryptodomex para el móvil)
required_packages = [   
    'fake_useragent', 
    'dropbox', 
    'requests',
    'cryptography',
    'pytz',
    'pycryptodomex' # Requerido estrictamente por mpcrypto (Cryptodome)
]

# Verificar e instalar paquetes
for package in required_packages:
    try:
        if package == 'pycryptodomex': __import__('Cryptodome')
        else: __import__(package)
    except ImportError:
        print(f"{package} no está instalado. Instalando...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
        except subprocess.CalledProcessError:
            print(f"Hubo un error al intentar instalar el paquete: {package}")

# Importaciones Generales
from datetime import datetime, timedelta
import json
import time
import logging
from logging.handlers import TimedRotatingFileHandler
import re
import base64
import uuid
import ssl
from urllib3.poolmanager import PoolManager
from requests.adapters import HTTPAdapter
from fake_useragent import UserAgent
import dropbox
from dropbox.files import WriteMode
import requests # Librería universal

# Importación limpia de MPCrypto
try:
    from mp_crypto import MPCrypto
except ImportError as e:
    print(f"[ERROR] Error crítico importando MPCrypto. Revisa que el archivo exista en {RUTA_MPCRYPTO}. Detalles: {e}")
    sys.exit(1)

# ---------------------------------------------------------
# COLORES Y ESTÉTICA DE CONSOLA
# ---------------------------------------------------------
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    WHITE = '\033[97m'
    RESET = '\033[0m'

class MovistarNuevaApi:
    
    def __init__(self):
        # ---------------------------------------------------------
        # ESTRUCTURA DE DIRECTORIOS Y LOGS
        # ---------------------------------------------------------
        self.directorio_ejecucion = SCRIPT_DIR
        
        directorios_necesarios = [
            os.path.join(self.directorio_ejecucion, "recursos", "cuenta"),
            os.path.join(self.directorio_ejecucion, "recursos", "canales"),
            os.path.join(self.directorio_ejecucion, "recursos", "log"),
            RUTA_MPCRYPTO,
            os.path.join(self.directorio_ejecucion, "recursos", "listas", "live")
        ]

        for directorio in directorios_necesarios:
            if not os.path.exists(directorio):
                os.makedirs(directorio)
                
        # Rutas Fijas
        self.ruta_fichero_creedenciales = os.path.join(self.directorio_ejecucion, "recursos", "cuenta", "creedenciales.json")
        self.ruta_fichero_informacion_dispositivos = os.path.join(self.directorio_ejecucion, "recursos", "cuenta", "dispositivos.json")
        self.ruta_fichero_informacion_cuenta = os.path.join(self.directorio_ejecucion, "recursos", "cuenta", "info_cuenta.json")
        self.ruta_fichero_json_informacion_canales = os.path.join(self.directorio_ejecucion, "recursos", "canales", "info_canales.json")
        self.ruta_fichero_log = os.path.join(self.directorio_ejecucion, "recursos", "log", "ejecucion.log")
        self.ruta_fichero_resultado = os.path.join(self.directorio_ejecucion, "recursos", "log", "resultado.txt")
        
        # Configuración de Logs
        log_handler = TimedRotatingFileHandler(self.ruta_fichero_log, when="D", interval=1, backupCount=7, encoding='utf-8')
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%d/%m/%Y %H:%M:%S', handlers=[log_handler])
        
        # Inicio de Interfaz
        self.ascii_clear()
        self.print_colored("[INICIO] Inicializando el sistema en Modo Consumo Universal (NUEVA API)...", Colors.CYAN)

        self.ua = UserAgent().random 
        
        # Endpoints Nueva API
        self.urls = {
            'login': 'https://soter-pf.sve.video.telefonicaservices.com/service/oidc/connect/token?deviceClass=webplayer',
            'account_info': 'https://soter-pf.sve.video.telefonicaservices.com/service/login/webplayer/accountInfo?legacy=true',
            'init_data': 'https://soter-pf.sve.video.telefonicaservices.com/service/login/initData?legacy=true',
            'put_device': 'https://soter-pf.sve.video.telefonicaservices.com/service/login/devices?deviceId={device_id}&deviceType=webplayer&accountId={account_nbr}&legacy=true',
            'devices': 'https://soterpe-pf.sve.video.telefonicaservices.com/service/session/clientzone/{account_nbr}/devices',
            'tcdn': 'https://soter-pf.sve.video.telefonicaservices.com/service/tcdnidserver/{account_nbr}/devices/webplayer/cdn/token/refresh',
            'informacion_canales': 'https://soteroc-pf.cdn.sve.video.telefonicaservices.com/service/contents/webplayer/DIFUSION/contents/epg'
        }

        # Inicialización de MPCrypto
        self.mp_crypto = MPCrypto(
            device_class="webplayer",
            config_url="https://ver.movistarplus.es/feed/conf.php?id=all",
            config_pattern=r"yomvi\.setupConf\((\{.*?\})\);"
        )
        
        if not os.path.exists(self.ruta_fichero_creedenciales):
            msg = f"No he encontrado el fichero [{self.ruta_fichero_creedenciales}]. Abortando ejecución."
            self.print_colored(f"❌ {msg}", Colors.RED)
            sys.exit(1)

        self.credenciales = self.cargar_json(self.ruta_fichero_creedenciales)
        self.verificar_configuracion()
        
        # Generar Device ID si no existe
        if not self.credenciales.get("movistar", {}).get("device_id"):
            nuevo_id = uuid.uuid4().hex
            self.credenciales["movistar"]["device_id"] = nuevo_id
            self.guardar_json(self.ruta_fichero_creedenciales, self.credenciales)
        self.device_id = self.credenciales["movistar"]["device_id"]
        
        # Cabeceras base Universales
        self.default_main_headers = {
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'es-ES,es;q=0.9',
            'Connection': 'keep-alive',
            'Origin': 'https://ver.movistarplus.es',
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        }
        
        # Iniciar sesión SSL modificada
        self.session = self.getSslSession()
        
        # Variables de reporte
        file_name_dropbox = self.credenciales.get("dropbox", {}).get("file_name", "Movistar.m3u")
        self.nombre_base_sin_ext = os.path.splitext(file_name_dropbox)[0]
        self.ruta_fichero_lista_live = os.path.join(self.directorio_ejecucion, "recursos", "listas", "live", file_name_dropbox)

        self.enlaces_dropbox = {}
        self.validez_token = "Desconocida"
        self.mensaje_telegram = ""

        # -------------------------------------------------------------------------
        # FLUJO DE EJECUCIÓN PRINCIPAL
        # -------------------------------------------------------------------------
        self.gestionar_sesion()
        
        self.token_diario = self.get_access_token_tcdn()
        if not self.token_diario:
            self.print_colored("   ❌ Error crítico: Sin token TCDN diario no se puede continuar.", Colors.RED)
            sys.exit(1)
            
        self.guardar_estado_sesion()

        self.print_colored("\n📡 Recuperando información de Canales (Directos)...", Colors.MAGENTA)
        lista_canales_json_hoy = self.get_informacion_canales()
        lista_canales_json_guardada = self.cargar_json(self.ruta_fichero_json_informacion_canales) or []
        self.comparar_canales(lista_canales_json_guardada, lista_canales_json_hoy)
        
        self.generar_lista_m3u(lista_canales_json_hoy)
        self.agregar_otros_proveedores()

        if self.credenciales.get("dropbox", {}).get("activo", False):
            self.upload_dropbox_file()
        else:
            self.print_colored("\n⚠️  Subida de M3U a Dropbox omitida.", Colors.YELLOW)

        self.finalizar_ejecucion()

    # ---------------------------------------------------------
    # ADAPTADOR SSL UNIVERSAL (Adiós curl_cffi)
    # ---------------------------------------------------------
    def getSslSession(self):
        context = ssl.create_default_context()
        context.set_ciphers('DEFAULT@SECLEVEL=1:TLSv1.2')
        if hasattr(context, "options"):
            context.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x00000004)
    
        class SSLAdapter(HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                kwargs['ssl_context'] = context
                return super().init_poolmanager(*args, **kwargs)

        session = requests.Session()
        adapter = SSLAdapter()
        session.mount('https://', adapter)
        return session

    # ---------------------------------------------------------
    # INTERFAZ Y ESTÉTICA DE CONSOLA
    # ---------------------------------------------------------
    def print_colored(self, text, color):
        texto_limpio = text.strip()
        if texto_limpio:
            logging.info(texto_limpio)
            
        try:
            print(f"{color}{text}{Colors.RESET}")
        except:
            try:
                print(text.encode('ascii', errors='replace').decode())
            except:
                pass

    def ascii_clear(self):
        os.system("cls" if os.name == "nt" else "clear")
        logging.info("=====================================================")
        logging.info("INICIANDO EJECUCIÓN DEL SCRIPT - MODO CONSUMO (LIVE ONLY)")
        logging.info("=====================================================")
        print(rf"""{Colors.CYAN}
                       
                  0000                                      
   0000         0000000                                     
  0000000      000000000       0000                         
 000000000     000000000       0000                         
 00000000000 000000  0000  000000000000                     
 00000000000000000   0000  000000000000                     
 000  00000000000    000       0000                         
 0000  0000000000    000       0000                         
  000   00000000                                            
  000 
                    
    Movistar + Live Only (NUEVA API)
        by Rikelme (2026) V.2.0
{Colors.RESET}""")

    # ---------------------------------------------------------
    # VERIFICACIÓN DE CONFIGURACIÓN
    # ---------------------------------------------------------
    def verificar_configuracion(self):
        tel = self.credenciales.get("telegram", {})
        if tel.get("activo", False):
            if not tel.get("bot_token") or not tel.get("chat_id"):
                self.print_colored("   ⚠️ [RECORDATORIO] Telegram está activo pero faltan datos.", Colors.YELLOW)
                
        dbx = self.credenciales.get("dropbox", {})
        if dbx.get("activo", False):
            if not dbx.get("app_key") or not dbx.get("app_secret") or not dbx.get("refresh_token") or not dbx.get("file_name"):
                self.print_colored("   ⚠️ [RECORDATORIO] Dropbox está activo pero faltan datos en sus credenciales.", Colors.YELLOW)
                
        opc = self.credenciales.get("opciones", {})
        if not opc.get("url_claves"):
            self.print_colored("   ⚠️ [RECORDATORIO] Falta la 'url_claves' en opciones. Los canales codificados no tendrán keys.", Colors.YELLOW)
            
        if not opc.get("url_catchup"):
            self.print_colored("   ⚠️ [RECORDATORIO] Falta la 'url_catchup' en opciones. Se usará el servidor antiguo por defecto.", Colors.YELLOW)

    # ---------------------------------------------------------
    # SESIÓN Y TOKENS
    # ---------------------------------------------------------
    def gestionar_sesion(self):
        self.print_colored("\n🔑 Verificando estado de la sesión (Nueva API)...", Colors.MAGENTA)
        mov = self.credenciales.get("movistar", {})
        forzar_refresh = mov.get("forzar_refresh", False)
        
        self.accessToken_init = mov.get("accessToken_init")
        self.account_nbr = mov.get("accountNumber")
        
        caducidad_init = self.decode_jwt_exp(self.accessToken_init) if self.accessToken_init else None
        necesita_login = False
        
        if not self.accessToken_init or not self.account_nbr or forzar_refresh or not caducidad_init:
            self.print_colored("   🔄 Actualizando sesión desde cero o petición forzada...", Colors.YELLOW)
            necesita_login = True
        elif (caducidad_init - int(time.time())) < 259200: # Menos de 3 días
            self.print_colored("   🔄 Renovando accessToken_init (faltan < 3 días)...", Colors.YELLOW)
            if not self.renovar_tokens_con_accessToken_init():
                necesita_login = True
            else:
                self.refrescar_tokens_respaldo()
        else:
            self.validez_token = datetime.fromtimestamp(caducidad_init).strftime('%d/%m/%Y %H:%M:%S')
            self.print_colored(f"   ✅ Sesión válida hasta: {self.validez_token}", Colors.GREEN)

        if necesita_login:
            access_token_login = self.login()
            if not access_token_login:
                self.print_colored("❌ Faltan credenciales o falló el login principal.", Colors.RED)
                sys.exit(1)
            
            self.account_nbr = self.get_account_nbr(access_token_login)
            if not self.account_nbr:
                self.print_colored("❌ No se pudo obtener el account_number de la API.", Colors.RED)
                sys.exit(1)
            
            if not self.put_device_id(access_token_login):
                self.print_colored("❌ No se pudo validar el device_id en la API.", Colors.RED)
                sys.exit(1)

            if not self.get_init_data(access_token_login):
                self.print_colored("   ⚠️ Init Data falló. Reintentando con nuevo device_id...", Colors.YELLOW)
                nuevo_id = uuid.uuid4().hex
                self.device_id = nuevo_id
                self.credenciales["movistar"]["device_id"] = nuevo_id
                self.guardar_json(self.ruta_fichero_creedenciales, self.credenciales)
                if not self.put_device_id(access_token_login) or not self.get_init_data(access_token_login):
                    self.print_colored("❌ Error crítico en get_init_data incluso con nuevo device_id. Saliendo.", Colors.RED)
                    sys.exit(1)

            cred_login = self.cargar_json(self.ruta_fichero_creedenciales)
            if cred_login:
                cred_login['movistar']['access_token_login'] = access_token_login
                self.guardar_json(self.ruta_fichero_creedenciales, cred_login)

            self.get_informacion_dispositivos()
            self.procesar_dispositivos_respaldo(access_token_login)

    def decode_jwt_exp(self, token):
        try:
            payload_b64 = token.split('.')[1]
            payload_b64 += '=' * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.b64decode(payload_b64).decode('utf-8'))
            return payload.get('exp')
        except: return None

    def login(self):
        self.print_colored("   ➤ Iniciando login principal...", Colors.CYAN)
        usuario = self.credenciales.get("movistar", {}).get("usuario")
        password = self.credenciales.get("movistar", {}).get("password")
        if not usuario or not password: return None

        data = {
            'grant_type': 'password', 'username': usuario, 'password': password,
            'scope': 'api', 'client_id': '491aafabb70d4644954d8fb21e0b93b1', 'client_secret': 'secret'
        }
        
        basic_token_str = f"{self.device_id}:webplayer"
        basic_token = base64.b64encode(basic_token_str.encode('utf-8')).decode('utf-8')
        signature = self.mp_crypto.get_signature("POST", self.urls['login'], basic_token, "Basic", data)

        headers = {**self.default_main_headers, 'Content-Type': 'application/x-www-form-urlencoded',
                   'Authorization': f'OPPlus Basic={basic_token},Signature={signature}'}

        try:
            resp = self.session.post(self.urls['login'], data=data, headers=headers, timeout=15)
            if resp.status_code == 200:
                self.print_colored("   ✅ Access Token (Login) obtenido.", Colors.GREEN)
                return resp.json().get('access_token')
            else: self.print_colored(f"   ❌ Error Login (Code {resp.status_code}): {resp.text}", Colors.RED)
        except Exception as e: self.print_colored(f"   ❌ Excepción HTTP en Login: {e}", Colors.RED)
        return None

    def get_account_nbr(self, access_token_login):
        signature = self.mp_crypto.get_signature("GET", self.urls['account_info'], access_token_login, "Bearer")
        headers = {**self.default_main_headers, 'Content-Type': 'application/json',
                   'Authorization': f'OPPlus Bearer={access_token_login},Signature={signature}'}
        try:
            resp = self.session.get(self.urls['account_info'], headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                with open(self.ruta_fichero_informacion_cuenta, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                return data['ofertas'][0]['accountNumber']
            else:
                self.print_colored(f"   ❌ Error Account Info (Code {resp.status_code}): {resp.text}", Colors.RED)
        except Exception as e:
            self.print_colored(f"   ❌ Excepción HTTP en Account Info: {e}", Colors.RED)
        return None

    def put_device_id(self, access_token_login):
        url = self.urls['put_device'].format(device_id=self.device_id, account_nbr=self.account_nbr)
        signature = self.mp_crypto.get_signature("PUT", url, access_token_login, "Bearer")
        headers = {**self.default_main_headers, 'Content-Type': 'application/json',
                   'Authorization': f'OPPlus Bearer={access_token_login},Signature={signature}'}
        try:
            resp = self.session.put(url, headers=headers, timeout=15)
            if resp.status_code in (200, 201, 409):
                self.print_colored("   ✅ Device ID validado en la API.", Colors.GREEN)
                return True
            else:
                self.print_colored(f"   ❌ Error Put Device (Code {resp.status_code}): {resp.text}", Colors.RED)
        except Exception as e:
            self.print_colored(f"   ❌ Excepción HTTP en Put Device: {e}", Colors.RED)
        return False

    def get_init_data(self, access_token_login):
        self.print_colored("   ➤ Extrayendo Init Data...", Colors.CYAN)
        data = {
            "accountNumber": str(self.account_nbr), "sessionUserProfile": 0, "isKidProfile": False,
            "deviceId": str(self.device_id), "streamMiscellanea": "HTTPS", "deviceManufacturerProduct": "Chrome",
            "streamDRM": "Widevine", "streamFormat": "DASH"
        }
        signature = self.mp_crypto.get_signature("POST", self.urls['init_data'], access_token_login, "Bearer")
        headers = {**self.default_main_headers, 'Content-Type': 'application/json',
                   'Authorization': f'OPPlus Bearer={access_token_login},Signature={signature}'}
        
        try:
            resp = self.session.post(self.urls['init_data'], headers=headers, json=data, timeout=15)
            if resp.status_code == 200:
                self.accessToken_init = resp.json().get('accessToken')
                self.print_colored("   ✅ Token Init guardado en memoria.", Colors.GREEN)
                return True
            else:
                self.print_colored(f"   ❌ Error Init Data (Code {resp.status_code}): {resp.text}", Colors.RED)
        except Exception as e:
            self.print_colored(f"   ❌ Excepción HTTP en Init Data: {e}", Colors.RED)
        return False

    def _intentar_renovar_token(self, token, device_id):
        """Intenta renovar un accessToken_init para un device_id específico"""
        data = {
            "accountNumber": str(self.account_nbr), "sessionUserProfile": 0, "isKidProfile": False,
            "deviceId": str(device_id), "streamMiscellanea": "HTTPS", "deviceManufacturerProduct": "Chrome",
            "streamDRM": "Widevine", "streamFormat": "DASH"
        }
        signature = self.mp_crypto.get_signature("POST", self.urls['init_data'], token, "Bearer")
        headers = {**self.default_main_headers, 'Content-Type': 'application/json',
                   'Authorization': f'OPPlus Bearer={token},Signature={signature}'}
        try:
            resp = self.session.post(self.urls['init_data'], headers=headers, json=data, timeout=30)
            if resp.status_code == 200:
                self.accessToken_init = resp.json().get('accessToken')
                self.device_id = device_id
                return True
        except:
            pass
        return False

    def renovar_tokens_con_accessToken_init(self):
        # Primero intentar con el token/dispositivo actual
        if self._intentar_renovar_token(self.accessToken_init, self.device_id):
            self.print_colored("   ✅ Init Token renovado sin Login.", Colors.GREEN)
            return True

        # Si falla, intentar con tokens de respaldo
        self.print_colored("   ⚠️ No se pudo renovar con dispositivo actual. Probando respaldos...", Colors.YELLOW)
        cred = self.cargar_json(self.ruta_fichero_creedenciales)
        if cred:
            respaldos = cred.get('movistar', {}).get('dispositivos_respaldo', [])
            for disp in respaldos:
                did = disp.get('device_id')
                token = disp.get('accessToken_init')
                if did and token and did != self.device_id:
                    self.print_colored(f"   🔄 Probando respaldo: {did[:8]}...", Colors.CYAN)
                    if self._intentar_renovar_token(token, did):
                        self.print_colored(f"   ✅ Token renovado con dispositivo de respaldo: {did[:8]}...", Colors.GREEN)
                        cred2 = self.cargar_json(self.ruta_fichero_creedenciales)
                        if cred2:
                            for d in cred2['movistar'].get('dispositivos_respaldo', []):
                                if d['device_id'] == did:
                                    d['accessToken_init'] = self.accessToken_init
                                    break
                            self.guardar_json(self.ruta_fichero_creedenciales, cred2)
                        return True
                    time.sleep(1)
        self.print_colored("   ❌ No se pudo renovar con ningún token de respaldo.", Colors.RED)
        return False

    def get_access_token_tcdn(self):
        self.print_colored("   ➤ Solicitando TCDN (Token Diario)...", Colors.CYAN)
        url = self.urls['tcdn'].format(account_nbr=self.account_nbr)
        signature = self.mp_crypto.get_signature("POST", url, self.accessToken_init, "Bearer")
        headers = {**self.default_main_headers, 'Content-Type': 'application/json',
                   'Authorization': f'OPPlus Bearer={self.accessToken_init},Signature={signature}'}
        try:
            resp = self.session.post(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                self.print_colored("   ✅ TCDN obtenido con éxito.", Colors.GREEN)
                return resp.json().get('access_token')
            else:
                self.print_colored(f"   ❌ Error Obteniendo TCDN (Code {resp.status_code}): {resp.text}", Colors.RED)
        except Exception as e:
            self.print_colored(f"   ❌ Excepción HTTP Obteniendo TCDN: {e}", Colors.RED)
        return None

    def get_informacion_dispositivos(self):
        url = self.urls['devices'].format(account_nbr=self.account_nbr)
        signature = self.mp_crypto.get_signature("GET", url, self.accessToken_init, "Bearer")
        headers = {**self.default_main_headers, 'Content-Type': 'application/json',
                   'Authorization': f'OPPlus Bearer={self.accessToken_init},Signature={signature}',
                   'X-Movistarplus-Deviceid': self.device_id}
        try:
            resp = self.session.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                with open(self.ruta_fichero_informacion_dispositivos, 'w', encoding='utf-8') as f:
                    json.dump(resp.json(), f, indent=2, ensure_ascii=False)
        except: pass

    def obtener_init_para_dispositivo(self, token, device_id):
        """Obtiene accessToken_init para un device_id específico usando un token (login o init)"""
        data = {
            "accountNumber": str(self.account_nbr), "sessionUserProfile": 0, "isKidProfile": False,
            "deviceId": str(device_id), "streamMiscellanea": "HTTPS", "deviceManufacturerProduct": "Chrome",
            "streamDRM": "Widevine", "streamFormat": "DASH"
        }
        signature = self.mp_crypto.get_signature("POST", self.urls['init_data'], token, "Bearer")
        headers = {**self.default_main_headers, 'Content-Type': 'application/json',
                   'Authorization': f'OPPlus Bearer={token},Signature={signature}'}
        try:
            resp = self.session.post(self.urls['init_data'], headers=headers, json=data, timeout=30)
            if resp.status_code == 200:
                return resp.json().get('accessToken')
        except:
            pass
        return None

    def procesar_dispositivos_respaldo(self, access_token_login):
        """Obtiene accessToken_init para TODOS los dispositivos de la cuenta y los guarda como respaldo"""
        self.print_colored("\n📌 Obteniendo tokens de respaldo para todos los dispositivos...", Colors.MAGENTA)

        url = self.urls['devices'].format(account_nbr=self.account_nbr)
        signature = self.mp_crypto.get_signature("GET", url, self.accessToken_init, "Bearer")
        headers = {**self.default_main_headers, 'Content-Type': 'application/json',
                   'Authorization': f'OPPlus Bearer={self.accessToken_init},Signature={signature}',
                   'X-Movistarplus-Deviceid': self.device_id}
        try:
            resp = self.session.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                self.print_colored("   ❌ No se pudo listar dispositivos.", Colors.RED)
                return
            dispositivos = resp.json()
        except Exception as e:
            self.print_colored(f"   ❌ Error listando dispositivos: {e}", Colors.RED)
            return

        if isinstance(dispositivos, dict):
            for clave in ['devices', 'deviceList', 'items', 'data', 'result']:
                if clave in dispositivos:
                    dispositivos = dispositivos[clave]
                    break
        if not isinstance(dispositivos, list) or len(dispositivos) == 0:
            self.print_colored("   ⚠️ No se encontraron dispositivos en la cuenta.", Colors.YELLOW)
            return

        self.print_colored(f"   ✅ {len(dispositivos)} dispositivo(s) encontrados. Obteniendo tokens...", Colors.GREEN)

        tokens_respaldo = []
        for i, disp in enumerate(dispositivos, 1):
            d_id = disp.get('Id') or disp.get('deviceId') or disp.get('id')
            d_type = disp.get('DeviceType', '')
            d_type_code = disp.get('DeviceTypeCode', '')

            if not d_id:
                continue

            if d_type_code in ["STB", "STB_IPTV", "IPTV"] or d_type in ["STB", "STB_IPTV", "IPTV"]:
                self.print_colored(f"   ⏭️  [{i}/{len(dispositivos)}] Omitiendo decodificador STB: {d_id[:8]}...", Colors.YELLOW)
                continue

            if d_id == self.device_id:
                self.print_colored(f"   ✅ [{i}/{len(dispositivos)}] Device actual ({d_id[:8]}...) ya tiene token.", Colors.GREEN)
                continue

            print(f"   [%d/%d] %-15s %s... -> obteniendo token..." % (i, len(dispositivos), d_type, d_id[:8]), end=" ")

            token = None
            if access_token_login:
                token = self.obtener_init_para_dispositivo(access_token_login, d_id)
            if not token:
                token = self.obtener_init_para_dispositivo(self.accessToken_init, d_id)

            if token:
                print("OK")
                tokens_respaldo.append({
                    'device_id': d_id,
                    'accessToken_init': token,
                    'device_type': d_type,
                    'device_type_code': d_type_code
                })
            else:
                print("fallo")

            time.sleep(1.5)

        if tokens_respaldo:
            cred = self.cargar_json(self.ruta_fichero_creedenciales)
            if cred:
                if 'dispositivos_respaldo' not in cred['movistar']:
                    cred['movistar']['dispositivos_respaldo'] = []

                ids_guardados = {t['device_id'] for t in cred['movistar']['dispositivos_respaldo']}
                nuevos = 0
                for t in tokens_respaldo:
                    if t['device_id'] not in ids_guardados:
                        cred['movistar']['dispositivos_respaldo'].append(t)
                        ids_guardados.add(t['device_id'])
                        nuevos += 1

                self.guardar_json(self.ruta_fichero_creedenciales, cred)
                self.print_colored(f"   ✅ {nuevos} token(s) de respaldo guardados en creedenciales.json.", Colors.GREEN)
                if nuevos > 0:
                    self.print_colored(f"   📌 Ahora tienes {len(ids_guardados)} dispositivo(s) de respaldo. Si cambian la contraseña, el script podrá renovar automáticamente.", Colors.CYAN)

    def refrescar_tokens_respaldo(self):
        """Renueva cada token de respaldo usando su propio accessToken_init (auto-renovación)"""
        self.print_colored("\n📌 Renovando tokens de respaldo ...", Colors.MAGENTA)

        cred = self.cargar_json(self.ruta_fichero_creedenciales)
        if not cred:
            return
        respaldos = cred.get('movistar', {}).get('dispositivos_respaldo', [])
        if not respaldos:
            self.print_colored("   ⚠️ No hay dispositivos de respaldo que renovar.", Colors.YELLOW)
            return

        actualizados = 0
        for i, disp in enumerate(respaldos, 1):
            did = disp.get('device_id')
            token = disp.get('accessToken_init')
            if not did or not token:
                continue

            print(f"   [%d/%d] %-15s %s... -> renovando..." % (i, len(respaldos), disp.get('device_type',''), did[:8]), end=" ")
            nuevo = self.obtener_init_para_dispositivo(token, did)
            if nuevo:
                disp['accessToken_init'] = nuevo
                actualizados += 1
                print("OK")
            else:
                print("fallo")
            time.sleep(1.5)

        if actualizados > 0:
            self.guardar_json(self.ruta_fichero_creedenciales, cred)
            self.print_colored(f"   ✅ {actualizados}/{len(respaldos)} token(s) de respaldo renovados en creedenciales.json.", Colors.GREEN)

    def guardar_estado_sesion(self):
        cred = self.cargar_json(self.ruta_fichero_creedenciales)
        if cred:
            cred['movistar']['accountNumber'] = self.account_nbr
            cred['movistar']['device_id'] = self.device_id
            cred['movistar']['accessToken_init'] = self.accessToken_init
            cred['movistar']['access_token_tcdn'] = self.token_diario
            cred['movistar']['forzar_refresh'] = False
            
            cad_ts = self.decode_jwt_exp(self.accessToken_init)
            if cad_ts:
                self.validez_token = datetime.fromtimestamp(cad_ts).strftime('%d/%m/%Y %H:%M:%S')
                cred['movistar']['accessToken_init_exp'] = self.validez_token
            
            for k in ['access_token', 'access_token_exp', 'token_diario', 'token_diario_exp']:
                if k in cred['movistar']: del cred['movistar'][k]
                
            self.guardar_json(self.ruta_fichero_creedenciales, cred)

    # ---------------------------------------------------------
    # SEGURIDAD Y DESCIFRADO
    # ---------------------------------------------------------
    def descifrar_url(self, url_cifrada: str) -> str:
        if not url_cifrada: return ""
        if url_cifrada.startswith("http://") or url_cifrada.startswith("https://"): return url_cifrada
        ruta_clave = os.path.join(self.directorio_ejecucion, "recursos", "cuenta", ".clave_fernet")
        if not os.path.exists(ruta_clave): return ""
        try:
            from cryptography.fernet import Fernet
            with open(ruta_clave, "rb") as f: clave = f.read().strip()
            return Fernet(clave).decrypt(url_cifrada.encode("utf-8")).decode("utf-8")
        except: return ""

    # ---------------------------------------------------------
    # DIRECTOS (M3U) CON LÓGICA DE SERVIDORES CATCHUP
    # ---------------------------------------------------------
    def get_informacion_canales(self):
        self.print_colored("   ➤ Descargando lista EPG de canales...", Colors.CYAN)
        try:
            r = self.session.get(self.urls['informacion_canales'], timeout=15)
            if r.status_code == 200:
                json_data = r.json()
                json_info = []
                for obj in json_data:
                    nombre_canal = obj.get("Nombre") or ""
                    if not nombre_canal:
                        continue
                    if not nombre_canal.startswith("Pruebas") and not nombre_canal.startswith("Test"):
                        json_info.append({
                            'nombre': obj.get("Nombre"),
                            'codigo_cadena': obj.get("CodCadenaTv"),
                            'dial': obj.get("Dial"),
                            'casId': obj.get("CasId"),
                            'logo': obj.get("Logo"),
                            'mpd': obj.get("PuntoReproduccion")
                        })
                return json_info
        except: pass
        return []

    def comparar_canales(self, lista_guardada, lista_hoy):
        dict1 = {(item['nombre']): item for item in lista_guardada}
        dict2 = {(item['nombre']): item for item in lista_hoy}
        with open(self.ruta_fichero_json_informacion_canales, 'w', encoding='utf-8') as salida:
            json.dump(list(dict2.values()), salida, indent=4, ensure_ascii=False)

    def generar_lista_m3u(self, json_data):
        self.print_colored("   ➤ Construyendo lista M3U (Obteniendo llaves y catchup en RAM)...", Colors.CYAN)
        
        # 1. Obtener llaves externas
        claves_memoria = {}
        url_claves_cifrada = self.credenciales.get('opciones', {}).get('url_claves', '')
        url_claves = self.descifrar_url(url_claves_cifrada) if url_claves_cifrada else ''
        
        if url_claves:
            try:
                response = requests.get(url_claves, timeout=15)
                if response.status_code == 200:
                    claves_memoria = json.loads(response.content)
                    self.print_colored("      ✅ Diccionario de claves cargado correctamente.", Colors.GREEN)
            except:
                self.print_colored("      ⚠️ Error al cargar claves externas. Se usarán canales en abierto.", Colors.YELLOW)

        # 2. Obtener Mapa de Servidores de Catchup
        cas_ids_nuevos = set()
        url_catchup_cifrada = self.credenciales.get('opciones', {}).get('url_catchup', '')
        url_catchup = self.descifrar_url(url_catchup_cifrada) if url_catchup_cifrada else ''

        if url_catchup:
            try:
                resp_catchup = requests.get(url_catchup, timeout=15)
                if resp_catchup.status_code == 200:
                    catchup_data = resp_catchup.json()
                    for cat in ["solo_nuevo"]:
                        for item in catchup_data.get(cat, []):
                            cas_id = item.get("cas_id")
                            if cas_id:
                                cas_ids_nuevos.add(str(cas_id))
                    self.print_colored("      ✅ Mapa de servidores catchup analizado correctamente.", Colors.GREEN)
            except Exception as e:
                self.print_colored("      ⚠️ Error al cargar el mapa de catchup. Se usará el servidor antiguo por defecto.", Colors.YELLOW)

        m3u_list = "#EXTM3U url-tvg=\"https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiatv_sincolor.xml.gz\"\n"
        
        fake_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        fake_start = f"{fake_date}T00:00:00Z"
        fake_end = f"{fake_date}T09:59:59Z"

        for obj in json_data:
            tvg_id = obj.get("codigo_cadena")
            tvg_name = obj.get("nombre") 
            tvg_logo = obj.get("logo")
            tvg_number = obj.get("dial")
            mpd = obj.get("mpd")
            casId = obj.get("casId")
            
            if not casId:
                if not tvg_name or not mpd:
                    continue
                m3u_list += f"\n#EXTINF:-1 group-title=\"Movistar\" tvg-logo=\"{tvg_logo}\" tvg-id=\"{tvg_id}\",{tvg_name}\n{mpd}\n"
                continue

            # Selección inteligente del servidor Catchup
            servidor_catchup_base = "https://cutv-wp8.cdn.telefonica.com"
            if str(casId) in cas_ids_nuevos:
                servidor_catchup_base = "https://cutvhcsmno-wp0.cdn.telefonica.com"
                
            catchup_url = f"{servidor_catchup_base}/{casId}/vxfmt=dp/Manifest.mpd?device_profile=DASH_TV_WIDEVINE&start_time={{start_iso}}&end_time={{end_iso}}"

            key_str = claves_memoria.get(str(casId), "")
            key_formatted = ""
            if key_str:
                if "{" in key_str: key_formatted = key_str
                elif ":" in key_str:
                    k, v = key_str.split(":", 1)
                    key_formatted = json.dumps({k.strip(): v.strip()}, separators=(',', ':'))
                else: key_formatted = key_str

            m3u_list += f"\n#EXTINF:-1 group-title=\"Movistar\" group-logo=\"https://estatico.emisiondof6.com/recorte/m-DP/wpmos/MPLUS\" catchup-source=\"{catchup_url}\" catchup-type=\"default\" catchup-days=\"40\" tvg-logo=\"{tvg_logo}\" ch-number=\"{tvg_number}\" tvg-id=\"{tvg_id}\",{tvg_name}\n"
            m3u_list += "#KODIPROP:inputstreamaddon=inputstream.adaptive\n"
            m3u_list += "#KODIPROP:inputstream.adaptive.manifest_type=mpd\n"
            m3u_list += "#KODIPROP:inputstream.adaptive.license_type=clearkey\n"
            if key_formatted:
                m3u_list += f"#KODIPROP:inputstream.adaptive.license_key={key_formatted}\n"
            
            m3u_list += f"#KODIPROP:inputstream.adaptive.stream_headers=X-TCDN-token={self.token_diario}\n"
            m3u_list += f'#EXTVLCOPT:http-user-agent="{self.ua}"\n'
            m3u_list += f"{mpd}\n"

        with open(self.ruta_fichero_lista_live, 'w', encoding ='utf8') as m3u_file: 
            m3u_file.write(m3u_list)
        self.print_colored("\n   ✅ Archivo M3U de canales generado correctamente.", Colors.GREEN)

    def agregar_otros_proveedores(self):
        url_cifrada = self.credenciales.get('opciones', {}).get('url_proveedores_externos', '')
        url_proveedores = self.descifrar_url(url_cifrada) if url_cifrada else ''
        
        if url_proveedores:
            try:
                response = requests.get(url_proveedores, timeout=15)
                if response.status_code == 200:
                    contenido = response.content.decode('utf-8')
                    with open(self.ruta_fichero_lista_live, 'a', encoding='utf-8') as base:
                        base.write("\n" + contenido)
                    self.print_colored("   ✅ Canales de otros proveedores añadidos correctamente (en RAM).", Colors.GREEN)
            except Exception as e:
                self.print_colored(f"   ⚠️ Error al cargar proveedores externos: {e}", Colors.YELLOW)

    # ---------------------------------------------------------
    # UPLOADS Y NOTIFICACIONES
    # ---------------------------------------------------------
    def upload_dropbox_file(self):
        self.print_colored("\n☁️  Subiendo lista principal Live a Dropbox...", Colors.CYAN)
        creds_dbx = self.credenciales.get("dropbox", {})
        try:
            dbx = dropbox.Dropbox(app_key=creds_dbx.get("app_key"), app_secret=creds_dbx.get("app_secret"), oauth2_refresh_token=creds_dbx.get("refresh_token"))
            ruta_dropbox = '/' + creds_dbx.get("file_name")
            
            with open(self.ruta_fichero_lista_live, 'rb') as f:
                dbx.files_upload(f.read(), ruta_dropbox, mode=WriteMode('overwrite'))
            
            try:
                shared_link = dbx.sharing_create_shared_link(ruta_dropbox)
                url_directa = shared_link.url.replace('dl=0', 'dl=1')
            except dropbox.exceptions.ApiError as err:
                if hasattr(err, 'error') and hasattr(err.error, 'is_shared_link_already_exists') and err.error.is_shared_link_already_exists():
                    links = dbx.sharing_list_shared_links(path=ruta_dropbox, direct_only=True).links
                    url_directa = links[0].url.replace('dl=0', 'dl=1') if links else "URL no recuperable"
                else: raise err

            self.print_colored(f"   ✅ Lista M3U subida a Dropbox: {url_directa}", Colors.GREEN)
            self.enlaces_dropbox['live'] = url_directa 
        except Exception as e:
            self.print_colored(f"   ❌ Error Dropbox M3U: {e}", Colors.RED)

    def finalizar_ejecucion(self):
        msg = f"📺 {self.nombre_base_sin_ext.upper()}:\n"
        if self.enlaces_dropbox.get('live'):
            msg += f"  └ 🔗 Directo: {self.enlaces_dropbox['live']}\n"
        
        msg += f"  └ 📅 Validez: {self.validez_token}\n"

        self.mensaje_telegram = msg

        if self.credenciales.get("telegram", {}).get("activo", False):
            self.enviar_mensaje_telegram()
            
        with open(self.ruta_fichero_resultado, 'w', encoding='utf-8') as f:
            f.write(self.mensaje_telegram)
            
        self.print_colored("\n✅ PROCESO COMPLETADO SATISFACTORIAMENTE.PAZ Y AMOR Y EL PLUS PARA EL SALON", Colors.GREEN)

    def enviar_mensaje_telegram(self):
        bot_token = self.credenciales.get("telegram", {}).get("bot_token")
        chat_id = self.credenciales.get("telegram", {}).get("chat_id")
        if bot_token and chat_id:
            try:
                requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", data={'chat_id': chat_id, 'text': self.mensaje_telegram, 'disable_web_page_preview': True}, timeout=15)
                self.print_colored("   ✅ Telegram enviado con éxito.", Colors.GREEN)
            except Exception as e:
                self.print_colored(f"   ❌ Error al enviar Telegram: {e}", Colors.RED)

    # ---------------------------------------------------------
    # UTILIDADES
    # ---------------------------------------------------------
    def cargar_json(self, ruta_fichero: str):
        if os.path.exists(ruta_fichero):
            with open(ruta_fichero, 'r', encoding='utf-8') as fichero: return json.load(fichero)
        return None

    def guardar_json(self, ruta_fichero: str, data: object):
        with open(ruta_fichero, 'w', encoding='utf-8') as fichero: json.dump(data, fichero, indent=4)

if __name__ == "__main__":
    MovistarNuevaApi()