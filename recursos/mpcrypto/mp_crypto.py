from __future__ import annotations
import base64
import hashlib
import hmac
import json
import random
import re
import time
import urllib.parse
import requests
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import unpad
try:
    from mock_date_converter import MockDateConverter
except ImportError:
    MockDateConverter = None

class MPCrypto:
    SALT_PREFIX = b"Salted__"
    BLOCK_SIZE = AES.block_size
    KEY_LENGTH = 32
    IV_LENGTH = 16
    SALT_LENGTH = 8
    ENCODING = "utf-8"
    CIPHER_MODE = AES.MODE_CBC
    HASH_FUNCTION = hashlib.md5

    DEVICE_WEBPLAYER = "webplayer"
    DEVICE_ANDROID_TV = "android.tv"
    DEVICE_PHONE_ANDROID = "phone.android"
    DEVICE_TABLET_ANDROID = "tablet.android"

    _PHONE_REQUIRED_KEYS = {
        "value_phone_hours",
        "value_phone_minutes",
        "value_phone_seconds",
        "key_phone_hours",
        "key_phone_minutes",
        "key_phone_seconds",
    }

    _TABLET_REQUIRED_KEYS = {
        "value_tablet_hours",
        "value_tablet_minutes",
        "value_tablet_seconds",
        "key_tablet_hours",
        "key_tablet_minutes",
        "key_tablet_seconds",
    }

    def __init__(self, device_class: str, *, config_url: str | None = None, config_pattern: str | None = None, mock_date_converter: MockDateConverter | None = None):
        self.device_class = device_class
        self.mock_date_converter = mock_date_converter

        valid_devices = {
            self.DEVICE_WEBPLAYER,
            self.DEVICE_ANDROID_TV,
            self.DEVICE_PHONE_ANDROID,
            self.DEVICE_TABLET_ANDROID,
        }
        if device_class not in valid_devices:
            raise ValueError(f"Unsupported device_class: {device_class}")

        if device_class in {self.DEVICE_WEBPLAYER, self.DEVICE_ANDROID_TV}:
            if not config_url or not config_pattern:
                raise ValueError("config_url and config_pattern are required for webplayer/android.tv")

            self.CONFIG_URL = config_url
            self.CONFIG_PATTERN = config_pattern

            if device_class == self.DEVICE_WEBPLAYER:
                self.config = self.fetch_config_webplayer()
            else:
                self.config = self.fetch_config_androidtv()

            self.password = self.generate_password()
            self.consumer_secret = self.decrypt_ua("param")
            self.consumer_key = self.decrypt_ua("query")
            self.jswbw = self.decrypt_ua("jswbw")

            return

        if mock_date_converter is None:
            raise ValueError("mock_date_converter is required for phone.android / tablet.android")

        self._validate_mock_date_converter(mock_date_converter, device_class)
        self.mock_date_converter = mock_date_converter

        self.consumer_secret = self.reconstruct_app_consumer_secret()
        self.consumer_key = self.reconstruct_app_consumer_key()

    def _validate_mock_date_converter(self, mock_date_converter: MockDateConverter, device_class: str) -> None:
        package_name = getattr(mock_date_converter, "package_name", None)
        if not package_name:
            raise ValueError("mock_date_converter.package_name must be set")

        xor_templates = getattr(mock_date_converter, "xor_templates", None)
        if not xor_templates:
            raise ValueError("mock_date_converter.xor_templates must be populated before use")

        required = self._PHONE_REQUIRED_KEYS if device_class == self.DEVICE_PHONE_ANDROID else self._TABLET_REQUIRED_KEYS
        missing = required - xor_templates.keys()
        if missing:
            raise ValueError(f"Missing XOR templates for {device_class}: {sorted(missing)}")


    def get_basic_token(self, device_id: str) -> str:
        token_str = f"{device_id}:{self.device_class}"
        return base64.b64encode(token_str.encode(self.ENCODING)).decode(self.ENCODING)

    def fetch_config_webplayer(self) -> dict:
        response = requests.get(self.CONFIG_URL, timeout=10).text
        match = re.search(self.CONFIG_PATTERN, response, re.DOTALL)
        if not match:
            raise ValueError("Configuration pattern not found in the response.")

        config_data = json.loads(match.group(1))['config']
        return {
            "version": config_data['version'],
            "timestamp": config_data['timestamp'],
            "ua": config_data['ua'],
            "name": config_data['name'],
            "language": config_data['language']
        }

    def generate_password(self) -> str:
        version = self.config['version']
        timestamp = self.config['timestamp']
        name = self.config['name']
        language = self.config['language']
        password_str = f"{version}{name}{timestamp}{language}"
        encoded_password = base64.b64encode(password_str.encode(self.ENCODING)).decode(self.ENCODING)
        return encoded_password

    def fetch_config_androidtv(self) -> dict:
        response = requests.get(self.CONFIG_URL, timeout=10).text
        match = re.search(self.CONFIG_PATTERN, response, re.DOTALL)
        if not match:
            raise ValueError("Configuration pattern not found in the response.")

        ua_body = match.group(1)

        pairs = re.finditer(r'(\w+)\s*:\s*(?:\'([^\']*)\'|"([^"]*)")', ua_body)
        config_data = {
            p.group(1): (p.group(2) if p.group(2) is not None else p.group(3))
            for p in pairs
        }

        return {
            "version": config_data['version'],
            "timestamp": config_data['timestamp'],
            "ua": {
                "query": config_data['query'],
                "param": config_data['param'],
                "jswbw": config_data['jswbw']
            },
            "name": config_data['name'],
            "language": config_data['language']
        }

    def reconstruct_app_consumer_secret(self) -> str:
        mock_date_converter = self.mock_date_converter
        if(self.device_class == self.DEVICE_PHONE_ANDROID):
            hours = mock_date_converter.get_value_phone_hours()
            minutes = mock_date_converter.get_value_phone_minutes()
            seconds = mock_date_converter.get_value_phone_seconds()
        elif(self.device_class == self.DEVICE_TABLET_ANDROID):
            hours = mock_date_converter.get_value_tablet_hours()
            minutes = mock_date_converter.get_value_tablet_minutes()
            seconds = mock_date_converter.get_value_tablet_seconds()
        else:
            raise ValueError("Incorrect device_class for this function.")
        return hours + minutes + seconds

    def reconstruct_app_consumer_key(self) -> str:
        mock_date_converter = self.mock_date_converter
        if(self.device_class == self.DEVICE_PHONE_ANDROID):
            hours = mock_date_converter.get_key_phone_hours()
            minutes = mock_date_converter.get_key_phone_minutes()
            seconds = mock_date_converter.get_key_phone_seconds()
        elif(self.device_class == self.DEVICE_TABLET_ANDROID):
            hours = mock_date_converter.get_key_tablet_hours()
            minutes = mock_date_converter.get_key_tablet_minutes()
            seconds = mock_date_converter.get_key_tablet_seconds()
        else:
            raise ValueError("Incorrect device_class for this function.")
        return hours + minutes + seconds
    
    def decrypt_ua(self, key: str) -> str:
        try:
            encrypted_data = json.loads(self.config['ua'][key])
        except KeyError as e:
            raise KeyError(f"UA key '{key}' not found in config") from e
        return self.decrypt(encrypted_data, self.password)

    @classmethod
    def openssl_evp_bytes_to_key(cls, password: str, salt: bytes) -> tuple:
        password_bytes = password.encode(cls.ENCODING)
        key_iv = b''
        prev = b''
        while len(key_iv) < cls.KEY_LENGTH + cls.IV_LENGTH:
            prev = cls.HASH_FUNCTION(prev + password_bytes + salt).digest()
            key_iv += prev
        key = key_iv[:cls.KEY_LENGTH]
        iv = key_iv[cls.KEY_LENGTH:cls.KEY_LENGTH + cls.IV_LENGTH]
        return key, iv

    @classmethod
    def _decode_segment(cls, segment: list[str]) -> bytes:
        return bytes.fromhex(''.join(segment[::-1]))

    @classmethod
    def _extract_salt_and_ciphertext(cls, data: bytes) -> tuple[bytes, bytes]:
        if data.startswith(cls.SALT_PREFIX):
            if len(data) < len(cls.SALT_PREFIX) + cls.SALT_LENGTH:
                raise ValueError("Invalid salted ciphertext: truncated salt")

            salt = data[len(cls.SALT_PREFIX):len(cls.SALT_PREFIX) + cls.SALT_LENGTH]
            ciphertext = data[len(cls.SALT_PREFIX) + cls.SALT_LENGTH:]
        else:
            salt = b''
            ciphertext = data
        return salt, ciphertext

    @classmethod
    def _decrypt_ciphertext(cls, ciphertext: bytes, password: str, salt: bytes) -> bytes:
        key, iv = cls.openssl_evp_bytes_to_key(password, salt)
        cipher = AES.new(key, cls.CIPHER_MODE, iv)
        return unpad(cipher.decrypt(ciphertext), cls.BLOCK_SIZE)

    @classmethod
    def decrypt(cls, salt_ciphertext_segments: list[list[str]], password: str) -> str:
        decrypted_parts = []

        for segment in salt_ciphertext_segments:
            raw_bytes = cls._decode_segment(segment)
            decoded = base64.b64decode(raw_bytes.decode(cls.ENCODING))

            salt, ciphertext = cls._extract_salt_and_ciphertext(decoded)
            plaintext_bytes = cls._decrypt_ciphertext(ciphertext, password, salt)

            decrypted_parts.append(plaintext_bytes.decode(cls.ENCODING))

        return ''.join(decrypted_parts)

    @staticmethod
    def get_nonce_web() -> str:
        random_part = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=11))
        timestamp_part = str(int(time.time() * 1000))
        full_nonce = random_part + timestamp_part
        return base64.b64encode(full_nonce.encode('utf-8')).decode('utf-8')
    
    @staticmethod
    def get_nonce_apk() -> str:
        random_part = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', k=9))
        return random_part

    @staticmethod
    def get_hmac_sha1(key: bytes, message: str) -> str:
        signature = hmac.new(key, message.encode(), hashlib.sha1)
        return base64.b64encode(signature.digest()).decode()

    def get_signature(self, method: str, url: str, token: str, scheme: str, params: dict | None = None) -> str:
        method = method.upper()
        allowed_methods = {"GET", "POST", "PUT", "DELETE"}
        allowed_schemes = {"Basic", "Bearer"}

        if method not in allowed_methods:
            raise ValueError(f"Invalid method: {method}. Allowed methods are: {allowed_methods}")
        if scheme not in allowed_schemes:
            raise ValueError(f"Invalid scheme: {scheme}. Allowed schemes are: {allowed_schemes}")

        consumer_secret = self.consumer_secret.encode('utf-8')
        consumer_key = self.consumer_key

        if self.device_class in [self.DEVICE_WEBPLAYER, self.DEVICE_ANDROID_TV]:
            nonce = self.get_nonce_web()
        else:
            nonce = self.get_nonce_apk()

        signature_method = "HMAC-SHA1"
        timestamp = str(int(time.time()))
        version = "1.0"

        parsed_url = urllib.parse.urlparse(url)
        base_url = parsed_url.netloc + parsed_url.path

        url_params = dict(urllib.parse.parse_qsl(parsed_url.query))

        merged_params = {}
        if params:
            merged_params.update(params)
        merged_params.update(url_params)

        merged_params[scheme] = token
        merged_params['consumer_key'] = consumer_key
        merged_params['nonce'] = nonce
        merged_params['signature_method'] = signature_method
        merged_params['timestamp'] = timestamp
        merged_params['version'] = version

        for key in list(merged_params.keys()):
            raw_value = str(merged_params[key])
            decoded_value = urllib.parse.unquote(raw_value)

            if '@' in decoded_value:
                merged_params[key] = urllib.parse.quote_plus(decoded_value)
            else:
                merged_params[key] = raw_value

        sorted_encoded_params = []
        for key in sorted(merged_params.keys()):
            encoded_key = urllib.parse.quote_plus(key)
            encoded_value = urllib.parse.quote_plus(merged_params[key])
            sorted_encoded_params.append(f"{encoded_key}%3D{encoded_value}")

        encoded_sorted_params = "%26".join(sorted_encoded_params)
        data_to_sign = f"{method}&{urllib.parse.quote_plus(base_url)}&{encoded_sorted_params}"

        hmac_sha1 = self.get_hmac_sha1(consumer_secret, data_to_sign)

        result_string = (
            f'consumer_key="{consumer_key}",'
            f'nonce="{nonce}",'
            f'signature_method="{signature_method}",'
            f'signature="{hmac_sha1}",'
            f'timestamp="{timestamp}",'
            f'version="{version}"'
        )

        return base64.b64encode(result_string.encode()).decode()