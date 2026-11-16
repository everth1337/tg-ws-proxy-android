"""Small streaming AES-CTR adapter backed by Android's JCA provider."""
from java import jclass, jarray, jbyte

_JavaCipher = jclass('javax.crypto.Cipher')
_Key = jclass('javax.crypto.spec.SecretKeySpec')
_Iv = jclass('javax.crypto.spec.IvParameterSpec')

class algorithms:
    class AES:
        def __init__(self, key):
            if len(key) not in (16, 24, 32):
                raise ValueError('AES key must be 16/24/32 bytes')
            self.key = bytes(key)

class modes:
    class CTR:
        def __init__(self, iv):
            if len(iv) != 16:
                raise ValueError('CTR IV must be 16 bytes')
            self.iv = bytes(iv)

class _Stream:
    def __init__(self, key, iv):
        self.cipher = _JavaCipher.getInstance('AES/CTR/NoPadding')
        self.cipher.init(_JavaCipher.ENCRYPT_MODE, _Key(jarray(jbyte)(key), 'AES'), _Iv(jarray(jbyte)(iv)))

    def update(self, data):
        if not data:
            return b''
        output = self.cipher.update(jarray(jbyte)(bytes(data)))
        return bytes(output) if output is not None else b''

class Cipher:
    def __init__(self, algorithm, mode):
        if not isinstance(algorithm, algorithms.AES) or not isinstance(mode, modes.CTR):
            raise TypeError('Only AES-CTR is supported')
        self.key, self.iv = algorithm.key, mode.iv

    def encryptor(self):
        return _Stream(self.key, self.iv)

    decryptor = encryptor
