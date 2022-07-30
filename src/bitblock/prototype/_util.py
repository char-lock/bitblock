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
    _byte_sz: int = int(bit_sz / 8)
    _x_sz: int = len(x)
    if _x_sz == 0:
        return uint8(0x00)
    _value: int = 0x00
    if _x_sz > _byte_sz:
        raise OverflowError("Provided `x` is larger than requested `bit_sz`.")
    for _b in range(_byte_sz):
        _shift: int = 8 * (_byte_sz - ((_b + 1) + (_byte_sz - _x_sz)))
        if _shift < 0 or _shift > bit_sz - 8:
            print(f"{_byte_sz} - (({_b} + 1) + ({_byte_sz} - {_x_sz}))")
        _v: int = x[_x_sz - 1 - _b] if _b <= _x_sz else 0x00
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
        if int(_value.byteswap()) < int(0x100000000):
            raise ValueError("Not canonical. Encoding too large. 64-bit used.")
    elif _disc == uint8(0xfe):
        _value: uint32 = pack_bytes(block.read(4), 32, False)
        if _value.byteswap() < int(0x10000):
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
    _version: uint32 = pack_bytes(block.read(4), 32, False)
    _tx_in_sz: int_t = read_var_int(block)
    print(_tx_in_sz)
    _tx_in: List = list()
    for _i in range(_tx_in_sz):
        _hash: str = endian_swap(block.read(32)).hex()
        _index: uint32 = pack_bytes(block.read(4), 32, False)
        _script_sz: int_t = read_var_int(block)
        _sig_script_buffer: List = list()
        _script_sz_mut = int(_script_sz)
        print(_script_sz_mut)
        while _script_sz_mut > 0:
            if _script_sz_mut >= 0xffffffff:
                _script_sz_mut -= 0xffffffff
                _sig_script_buffer.append(block.read(0xffffffff).hex())
            else:
                _sig_script_buffer.append(block.read(_script_sz_mut).hex())
                _script_sz_mut = 0
        _sig_script = ''.join(_sig_script_buffer)
        _sequence: uint32 = pack_bytes(block.read(4), 32, False)
        _tx_in.append([_hash, _index, _script_sz, _sig_script, _sequence])
    _tx_out_sz: int_t = read_var_int(block)
    _tx_out: List = list()
    for _i in range(_tx_out_sz):
        _value: uint64 = pack_bytes(block.read(8), 64, False)
        _script_sz: int_t = read_var_int(block)
        _pk_script_buffer: List = list()
        _script_sz_mut = int(_script_sz)
        while _script_sz_mut > 0:
            if _script_sz_mut >= 0xffffffff:
                _script_sz_mut -= 0xffffffff
                _pk_script_buffer.append(block.read(0xffffffff).hex())
            else:
                _pk_script_buffer.append(block.read(_script_sz_mut).hex())
                _script_sz_mut = 0
        _pk_script = ''.join(_pk_script_buffer)
        _tx_out.append([_value, _script_sz, _pk_script])
    _lock_time: uint32 = pack_bytes(block.read(4), 32, False)
    return {
        "version": _version,
        "tx_in_sz": _tx_in_sz,
        "tx_in": _tx_in,
        "tx_out_sz": _tx_out_sz,
        "tx_out": _tx_out,
        "lockTime": _lock_time
    }

def read_all_tx(block: BufferedReader, tx_sz: int_t) -> List:
    """ Reads and returns a list of all transactions in the block. """
    _tx: List = list()
    for _i in range(tx_sz):
        print(_i)
        _tx.append(decode_tx(block))
    return _tx

def endian_swap(b: bytes) -> bytes:
    _new = list()
    for i in range(len(b)):
        _new.append(b[len(b) - 1 - i])
    return bytes(_new)
