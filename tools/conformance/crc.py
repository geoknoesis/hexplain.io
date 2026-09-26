"""The Rocksoft ("Williams") parameterised CRC model, the one bddo:CustomCrc and the named CRC
algorithms of BDDO are stated in.

A CRC is fixed by six parameters: its width in bits, its polynomial (the generator without its
top bit), the register's initial value, whether each input byte is reflected (least-significant
bit first), whether the final register is reflected, and a value XORed into the result. The
catalogue check value is the CRC of the nine ASCII bytes "123456789".

Both the conformance suite (tools/conformance/cases_*.py) and the catalogue gate
(tools/test_crc_catalogue.py) compute CRCs with this one function, bit by bit, so that nothing
depends on a table or a third-party package.
"""

CHECK_INPUT = b"123456789"


def reflect(value, width):
    """`value`'s low `width` bits in reverse order."""
    out = 0
    for _ in range(width):
        out = (out << 1) | (value & 1)
        value >>= 1
    return out


def crc(data, width, poly, init, refin, refout, xorout):
    """The CRC of `data` under the Rocksoft model."""
    if not 8 <= width <= 64:
        raise ValueError("width is 8..64")
    top = 1 << (width - 1)
    mask = (1 << width) - 1
    for name, value in (("poly", poly), ("init", init), ("xorout", xorout)):
        if not 0 <= value <= mask:
            raise ValueError(f"{name} is a non-negative integer below 2^width")
    register = init
    for byte in data:
        if refin:
            byte = reflect(byte, 8)
        register ^= byte << (width - 8)
        for _ in range(8):
            register = ((register << 1) ^ poly) & mask if register & top else (register << 1) & mask
    if refout:
        register = reflect(register, width)
    return register ^ xorout


#: The named algorithms: BDDO individual -> (HDL name, catalogue name, width, poly, init, refin, refout, xorout,
#: check). Parameters and check values are those of the CRC catalogue (Greg Cook, "Catalogue of parametrised
#: CRC algorithms", reveng.sourceforge.io/crc-catalogue).
NAMED = {
    "crc8Smbus": ("crc8", "CRC-8/SMBUS", 8, 0x07, 0x00, False, False, 0x00, 0xF4),
    "crc16": ("crc16", "CRC-16/IBM-3740 (CCITT-FALSE)", 16, 0x1021, 0xFFFF, False, False, 0x0000, 0x29B1),
    "crc16Arc": ("crc16arc", "CRC-16/ARC", 16, 0x8005, 0x0000, True, True, 0x0000, 0xBB3D),
    "crc16Xmodem": ("crc16xmodem", "CRC-16/XMODEM", 16, 0x1021, 0x0000, False, False, 0x0000, 0x31C3),
    "crc16Modbus": ("crc16modbus", "CRC-16/MODBUS", 16, 0x8005, 0xFFFF, True, True, 0x0000, 0x4B37),
    "crc16X25": ("crc16x25", "CRC-16/IBM-SDLC (X-25)", 16, 0x1021, 0xFFFF, True, True, 0xFFFF, 0x906E),
    "crc32": ("crc32", "CRC-32/ISO-HDLC", 32, 0x04C11DB7, 0xFFFFFFFF, True, True, 0xFFFFFFFF, 0xCBF43926),
    "crc32c": ("crc32c", "CRC-32/ISCSI (CRC-32C)", 32, 0x1EDC6F41, 0xFFFFFFFF, True, True, 0xFFFFFFFF, 0xE3069283),
    "crc32Bzip2": ("crc32bzip2", "CRC-32/BZIP2", 32, 0x04C11DB7, 0xFFFFFFFF, False, False, 0xFFFFFFFF, 0xFC891918),
    "crc32Mpeg2": ("crc32mpeg2", "CRC-32/MPEG-2", 32, 0x04C11DB7, 0xFFFFFFFF, False, False, 0x00000000, 0x0376E6E7),
    "crc64Ecma182": ("crc64ecma", "CRC-64/ECMA-182", 64, 0x42F0E1EBA9EA3693, 0, False, False, 0, 0x6C40DF5F0B497347),
    "crc64Xz": ("crc64xz", "CRC-64/XZ", 64, 0x42F0E1EBA9EA3693, 0xFFFFFFFFFFFFFFFF, True, True,
                0xFFFFFFFFFFFFFFFF, 0x995DC9BBDF1939FA),
}


def named(name, data):
    """The CRC of `data` under the named algorithm `name` (a BDDO individual's local name)."""
    _hdl, _label, width, poly, init, refin, refout, xorout, _check = NAMED[name]
    return crc(data, width, poly, init, refin, refout, xorout)


for _name, _row in NAMED.items():
    assert named(_name, CHECK_INPUT) == _row[-1], _name
