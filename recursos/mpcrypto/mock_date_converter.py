from __future__ import annotations
import struct

class MockDateConverter:

    IV = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    ]

    def __init__(self, package_name: str, xor_templates: dict[str, bytes]):
        if not package_name:
            raise ValueError("package_name is required")

        if not xor_templates:
            raise ValueError("xor_templates must not be empty")

        self.package_name = package_name
        self.xor_templates = xor_templates

        self.K = [
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
            0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
            0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
            0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
            0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
            0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
            0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
            0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
            0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
            0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
            0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
            0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
            0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
            0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
            0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
            0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
        ]

    def right_rotate(self, value, shift):
        return ((value >> shift) | (value << (32 - shift))) & 0xFFFFFFFF

    def hash(self, message):
        h = list(self.IV)
        original_length = len(message)
        bit_length = original_length * 8
        message += b'\x80' + b'\x00' * ((56 - (original_length + 1) % 64) % 64)
        message += struct.pack('>Q', bit_length)
        for i in range(0, len(message), 64):
            chunk = message[i:i+64]
            w = [0] * 64
            for j in range(16):
                w[j] = struct.unpack('>I', chunk[j*4:j*4+4])[0]
            for j in range(16, 64):
                s0 = self.right_rotate(w[j-15], 7) ^ self.right_rotate(w[j-15], 18) ^ (w[j-15] >> 3)
                s1 = self.right_rotate(w[j-2], 17) ^ self.right_rotate(w[j-2], 19) ^ (w[j-2] >> 10)
                w[j] = (w[j-16] + s0 + w[j-7] + s1) & 0xFFFFFFFF
            a, b, c, d, e, f, g, h_temp = h
            for j in range(64):
                S1 = self.right_rotate(e, 6) ^ self.right_rotate(e, 11) ^ self.right_rotate(e, 25)
                ch = (e & f) ^ ((~e) & g)
                temp1 = (h_temp + S1 + ch + self.K[j] + w[j]) & 0xFFFFFFFF
                S0 = self.right_rotate(a, 2) ^ self.right_rotate(a, 13) ^ self.right_rotate(a, 22)
                maj = (a & b) ^ (a & c) ^ (b & c)
                temp2 = (S0 + maj) & 0xFFFFFFFF
                h_temp, g, f = g, f, e
                e = (d + temp1) & 0xFFFFFFFF
                d, c, b = c, b, a
                a = (temp1 + temp2) & 0xFFFFFFFF
            h = [(x + y) & 0xFFFFFFFF for x, y in zip(h, [a, b, c, d, e, f, g, h_temp])]
        return struct.pack('>8I', *h)

    def _compute(self, func_type):
        xor_template = self.xor_templates[func_type]
        hash_bytes = self.hash(self.package_name.encode())
        hex_str = hash_bytes.hex()
        data_bytes = hex_str.encode('latin-1')

        data = data_bytes[:len(xor_template)]
        result_bytes = bytes([a ^ b for a, b in zip(data, xor_template)])
        return result_bytes.decode('latin-1')

    def get_value_phone_hours(self):
        return self._compute('value_phone_hours')

    def get_value_phone_minutes(self):
        return self._compute('value_phone_minutes')

    def get_value_phone_seconds(self):
        return self._compute('value_phone_seconds')

    def get_value_tablet_hours(self):
        return self._compute('value_tablet_hours')

    def get_value_tablet_minutes(self):
        return self._compute('value_tablet_minutes')

    def get_value_tablet_seconds(self):
        return self._compute('value_tablet_seconds')

    def get_key_phone_hours(self):
        return self._compute('key_phone_hours')

    def get_key_phone_minutes(self):
        return self._compute('key_phone_minutes')

    def get_key_phone_seconds(self):
        return self._compute('key_phone_seconds')

    def get_key_tablet_hours(self):
        return self._compute('key_tablet_hours')

    def get_key_tablet_minutes(self):
        return self._compute('key_tablet_minutes')

    def get_key_tablet_seconds(self):
        return self._compute('key_tablet_seconds')
    
    def get_key_demo_indigital(self):
        return self._compute('key_demo_indigital')

    def get_key_prod_indigital(self):
        return self._compute('key_prod_indigital')

    def get_key_sender_demo_indigital(self):
        return self._compute('key_sender_demo_indigital')

    def get_key_sender_prod_indigital(self):
        return self._compute('key_sender_prod_indigital')
