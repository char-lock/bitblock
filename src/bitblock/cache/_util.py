""" bitblock.cache.util

Helper functions used as part of the cache module.

"""

from hashlib import sha256
from io import BufferedReader
from numpy import (
    uint8, int8,
    uint16, int16,
    uint32, int32,
    uint64, int64
)
from sys import byteorder
from typing import List, Literal, Optional, TypeAlias, Union


varint: TypeAlias = Union[
    uint8, int8,
    uint16, int16,
    uint32, int32,
    uint64, int64
]


def set_endian(b: bytes, order: Literal['little', 'big']) -> bytes:
    """ Checks what the current byteorder is, and swaps bytes if needed.


    ### Parameters
    --------------

    b: bytes
        bytes to swap if necessary
    
    order: Literal['little', 'big']
        desired endianness

    """
    if byteorder == order or len(b) <= 1:
        return b
    else:
        _t: List = list()
        for _i in range(len(b)):
            _t.append(b[len(b) - _i - 1])
        return bytes(_t)


def pack(
    x: bytes,
    bit_sz: Literal[8, 16, 32, 64],
    signed: Optional[bool] = False
) -> varint:
    """ Packs a provided bytes iterable into a single value.

    ### Parameters
    --------------

    x: bytes
        bytes iterable to pack into a value.
    
    byte_sz: Literal[8, 16, 32, 64]
        how many bits to use for a given value.

    signed: Optional[bool]
        whether the returned value is signed.

    """
    x: bytes = set_endian(x, 'big')
    _byte_sz: int = int(bit_sz / 8)
    _x_sz: int = len(x)
    if _x_sz == 0:
        return uint8(0x00)
    _value: int = 0x00
    if _x_sz > _byte_sz:
        raise OverflowError(
            "Provided `x` is larger than requested `bit_sz`"
        )
    for _b in range(_byte_sz):
        _shift: int = 8 * (_byte_sz - (_b + 1) - (_byte_sz - _x_sz))
        _v: int = x[_b] if _b <= _x_sz else 0x00
        _value |= _v << _shift
    if signed:
        if bit_sz == 8:
            return int8(_value)
        elif bit_sz == 16:
            return int16(_value)
        elif bit_sz == 32:
            return int32(_value)
        elif bit_sz == 64:
            return int64(_value)
        else:
            raise ValueError("Invalid `bit_sz` provided")
    else:
        if bit_sz == 8:
            return uint8(_value)
        elif bit_sz == 16:
            return uint16(_value)
        elif bit_sz == 32:
            return uint32(_value)
        elif bit_sz == 64:
            return uint64(_value)
        else:
            raise ValueError("Invalid `bit_sz` provided")


def read_varint(block: BufferedReader) -> varint:
    """ Reads a variable length integer from a BufferedReader.


    ### Parameters
    --------------

    block: BufferedReader
        where to read the varint from

    """
    _discriminant: uint8 = pack(block.read(1), 8)
    if _discriminant < uint8(0xfd):
        return _discriminant
    elif _discriminant == uint8(0xfd):
        _value: uint16 = pack(block.read(2), 16)
        if _value < uint16(0xfd):
            raise ValueError("Non-canonical value passed to varint.")
    elif _discriminant == uint8(0xfe):
        _value: uint32 = pack(block.read(4), 32)
        if _value < uint32(0x10000):
            raise ValueError("Non-canonical value passed to varint.")
    elif _discriminant == uint8(0xff):
        _value: uint64 = pack(block.read(8), 64)
        if _value < uint64(0x100000000):
            raise ValueError("Non-canonical value passed to varint.")
    return _value


def read_uint8(block: BufferedReader) -> uint8:
    """ Reads an 8-bit value from a BufferedReader.


    ### Parameters
    --------------
    
    block: BufferedReader
        where to read the value from
    
    """
    return pack(block.read(1), 8)


def read_uint16(block: BufferedReader) -> uint16:
    """ Reads a 16-bit value from a BufferedReader.


    ### Parameters
    --------------
    
    block: BufferedReader
        where to read the value from
    
    """
    return pack(block.read(2), 16)


def read_uint32(block: BufferedReader) -> uint32:
    """ Reads a 32-bit value from a BufferedReader.


    ### Parameters
    --------------
    
    block: BufferedReader
        where to read the value from
    
    """
    return pack(block.read(4), 32)


def read_uint64(block: BufferedReader) -> uint64:
    """ Reads a 64-bit value from a BufferedReader.


    ### Parameters
    --------------
    
    block: BufferedReader
        where to read the value from
    
    """
    return pack(block.read(8), 64)


def read_hash256(block: BufferedReader) -> str:
    """ Reads a 256-bit hash from a BufferedReader. """
    return set_endian(block.read(32), 'big').hex()


def sha256_2(x: bytes) -> bytes:
    """ Returns digest of using the sha256 operation twice.


    ### Parameters
    --------------

    x: bytes
        on what to apply sha256 twice
    
    """
    return set_endian(
        sha256(
            set_endian(
                sha256(x).digest(),
                'big'
            )
        ).digest(),
        'big'
    )