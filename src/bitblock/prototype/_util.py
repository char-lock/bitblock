""" bitblock.prototype._util

Useful helper functions that can be used in multiple parts of
prototype modules.

"""
from io import BufferedReader, BytesIO
from numpy import (
    uint8, int8,
    uint16, int16,
    uint32, int32,
    uint64, int64,
)
from typing import Literal, Optional, TypeAlias, Union, List, Dict
from sys import byteorder
from hashlib import sha256

int_t: TypeAlias = Union[
    uint8, int8,
    uint16, int16,
    uint32, int32,
    uint64, int64
]


def pack_bytes(
    x: bytes,
    bit_sz: Literal[8, 16, 32, 64],
    signed: Optional[bool] = False
) -> int_t:
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
        raise OverflowError("Provided `x` is larger than requested `bit_sz`.")
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


def read_var_int(block: BufferedReader) -> int_t:
    """ Reads a variable length integer from a BufferedReader.

    ### Parameters
    --------------

    block: BufferedReader
        where to read the int from

    """
    _disc: uint8 = pack_bytes(block.read(1), 8, False)
    if _disc == uint8(0xff):
        _value: uint64 = pack_bytes(block.read(8), 64, False)
        if _value < int(0x100000000):
            raise ValueError("Not canonical. Encoding too large. 64-bit used.")
    elif _disc == uint8(0xfe):
        _value: uint32 = pack_bytes(block.read(4), 32, False)
        if _value < int(0x10000):
            raise ValueError("Not canonical. Encoding too large. 32-bit used.")
    elif _disc == uint8(0xfd):
        _value: uint16 = pack_bytes(block.read(2), 16, False)
        if _value < int(0xfd):
            raise ValueError("Not canonical. Encoding too large. 16-bit used.")
    else:
        _value: uint8 = _disc
    return _value


def decode_tx(block: BufferedReader) -> Dict:
    """ Reads transactions from a BufferedReader.

    ### Parameters
    --------------

    block: BufferedReader
        where to read tx from
    
    tx_sz: int
        how many tx to read

    """
    _tx_start = block.tell()
    # Transaction :: Version
    _version: uint32 = pack_bytes(block.read(4), 32, False)
    _tx_pos = block.tell()
    # Transaction :: vIn
    _tx_in_pos = block.tell()
    _tx_marker = pack_bytes(block.read(1), 8, False)
    _tx_flag = pack_bytes(block.read(1), 8, False)
    _segwit = False
    if _tx_marker != 0 or _tx_flag != 1:
        block.seek(_tx_pos)
    else:
        _segwit = True
    _tx_in_pos = block.tell()
    _tx_in_sz: int_t = read_var_int(block)
    _tx_in: List = list()
    for _i in range(_tx_in_sz):
        _hash: str = set_endian(block.read(32), 'big').hex()
        _index: uint32 = pack_bytes(block.read(4), 32, False)
        _script_sz: int_t = read_var_int(block)
        # This is a hacky fix to handle whenever the _script_sz is greater
        # than an index-ranged integer.
        _sig_script_buffer: List = list()
        _script_sz_mutable: int = int(_script_sz)
        while _script_sz_mutable > 0:
            if _script_sz_mutable >= 0xffffffff:
                _script_sz_mutable -= 0xffffffff
                _sig_script_buffer.append(block.read(0xffffffff).hex())
            else:
                _sig_script_buffer.append(
                    block.read(_script_sz_mutable).hex()
                )
                _script_sz_mutable = 0
        _sig_script: str = ''.join(_sig_script_buffer)
        _sequence: uint32 = pack_bytes(block.read(4), 32, False)
        _tx_in.append([_hash, _index, _script_sz, _sig_script, _sequence])
    # Transaction :: vOut
    _tx_out_sz: int_t = read_var_int(block)
    _tx_out: List = list()
    for _i in range(_tx_out_sz):
        _value: uint64 = pack_bytes(block.read(8), 64, False)
        _script_sz: int_t = read_var_int(block)
        # Similar hack as above to monkey-patch large script_sz values.
        _pk_script_buffer: List = list()
        _script_sz_mutable: int = int(_script_sz)
        while _script_sz_mutable > 0:
            if _script_sz_mutable >= 0xffffffff:
                _script_sz_mutable -= 0xffffffff
                _pk_script_buffer.append(block.read(0xffffffff).hex())
            else:
                _pk_script_buffer.append(
                    block.read(_script_sz_mutable).hex()
                )
                _script_sz_mutable = 0
        _pk_script: str = ''.join(_pk_script_buffer)
        _tx_out.append([_value, _script_sz, _pk_script])
    # Transaction :: Segwit
    _segwit_pos = block.tell()
    if _segwit:
        for _i in range(_tx_in_sz):
            _num_op = read_var_int(block)
            for _n in range(_num_op):
                _op = read_var_int(block)
                _ = block.read(_op)
    raw_lock_time = pack_bytes(block.read(4), 32, False)
    _lock_time = raw_lock_time
    _tx_pos = block.tell()
    block.seek(_tx_start)
    if _segwit:
        raw_version = block.read(4)
        raw_in_out = block.read(_segwit_pos - _tx_in_pos)
        raw_bytes = raw_version + raw_in_out + raw_lock_time
    else:
        raw_bytes = block.read(_tx_pos - _tx_start)
    block.seek(_tx_pos)
    _tx_hash = sha256_2(raw_bytes).hex()
    return {
        "version": _version,
        "tx_in_sz": _tx_in_sz,
        "tx_in": _tx_in,
        "tx_out_sz": _tx_out_sz,
        "tx_out": _tx_out,
        "lockTime": _lock_time,
        "tx_hash": _tx_hash,
    }


def read_all_tx(block: BufferedReader, tx_sz: int_t) -> List:
    """ Reads and returns a list of all transactions in a provided block.


    ### Parameters
    --------------

    block: BufferedReader
        source for transaction details

    tx_sz: int_t
        count of transactions

    """
    _tx: List = list()
    for _i in range(tx_sz):
        _tx.append(decode_tx(block))
    return _tx


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


def sha256_2(x) -> bytes:
    """ Returns the value of x after hashing twice with sha256. """
    return set_endian(sha256(
        set_endian(sha256(x).digest(), 'big')
    ).digest(), 'big')


def reverse(x: str) -> str:
    """ Returns a reversed version of `x`.


    ### Parameters
    --------------

    x: str
        string to be reversed

    """
    _t = list()
    for _i in range(len(x)):
        _t.append(x[len(x) - _i - 1])
    return ''.join(_t)