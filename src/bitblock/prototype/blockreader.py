""" bitblock.prototype.blockreader

A module to parse raw block files.

"""
from numpy import int32, uint32, uint64
from typing import TypeAlias, List
from io import BufferedReader, FileIO, BytesIO
from _util import *
from guppy import hpy
from hashlib import sha256

hp = hpy()

BLOCK_DIR = r"E:\Bitcoin\blockchain\blocks"
MAGIC = uint32(0xf9beb4d9)

def open_block(blk):
    # Read from the requested blk file.
    _blk_dir = BLOCK_DIR + '\\' + blk + '.dat'
    _blk_ = FileIO(_blk_dir, mode="r")
    _blk  = BufferedReader(_blk_)
    # Check the first 32-bit value against the known validation value.
    _magic: uint32 = pack_bytes(_blk.read(4), 32, False)
    if int(_magic) != int(MAGIC):
        raise Exception("Incorrect start.")
    # Pull the first block from the file.
    _block_sz: uint32 = pack_bytes(_blk.read(4), 32, False)
    _block_: BytesIO = BytesIO(_blk.read(_block_sz))
    _block: BufferedReader = BufferedReader(_block_, _block_sz)
    # Process the block header.
    _version: uint32 = pack_bytes(_block.read(4), 32, False)
    _prev_block: str = _block.read(32).hex()
    _merkle_root: str = _block.read(32).hex()
    _time: int64 = int64(pack_bytes(_block.read(4), 32, False))
    _bits: uint32 = pack_bytes(_block.read(4), 32, False)
    _nonce: uint32 = pack_bytes(_block.read(4), 32, False)
    _block.seek(0, 0)
    _hash: str = sha256(sha256(_block.read(80)).digest()).hexdigest()
    print(f"""Hash: {_hash}
Version: {_version}
Previous Block: {_prev_block}
Merkle Root: {_merkle_root}
Time: {_time}
Bits: {_bits}
Nonce: {_nonce}""")
    # Process transactions
    _tx_sz: int_t = read_var_int(_block)
    print(f"Tx Count: {_tx_sz}")
    _tx: List = read_all_tx(_block, _tx_sz)
    print(f"Tx Length: {len(_tx)}")


def decode_tx(block: BufferedReader) -> List:
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
    _tx_in: List = list()
    for _i in range(_tx_in_sz):
        _hash: str = block.read(32).hex()
        _index: uint32 = pack_bytes(block.read(4), 32, False)
        _script_sz: int_t = read_var_int(block)
        _sig_script: str = block.read(_script_sz).hex()
        _sequence: uint32 = pack_bytes(block.read(4), 32, False)
        _tx_in.append([_hash, _index, _script_sz, _sig_script, _sequence])
    _tx_out_sz: int_t = read_var_int(block)
    _tx_out: List = list()
    for _i in range(_tx_out_sz):
        _value: uint64 = pack_bytes(block.read(8), 64, False)
        _script_sz: int_t = read_var_int(block)
        _pk_script: str = block.read(_script_sz).hex()
        _tx_out.append([_value, _script_sz, _pk_script])
    _lock_time: uint32 = pack_bytes(block.read(4), 32, False)
    return [_version, _tx_in_sz, _tx_in, _tx_out_sz, _tx_out, _lock_time]


def read_all_tx(block: BufferedReader, tx_sz: int_t) -> List:
    """ Reads and returns a list of all transactions in the block. """
    _tx: List = list()
    for _i in range(tx_sz):
        _tx.append(decode_tx(block))
    return _tx


open_block('blk02422')