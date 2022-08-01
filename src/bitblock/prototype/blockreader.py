""" bitblock.prototype.blockreader

A module to parse raw block files.

"""
from numpy import int32, uint32, uint64
from typing import Dict, TypeAlias, List
from io import BufferedReader, FileIO, BytesIO
from _util import *
from hashlib import sha256

BLOCK_DIR = r"E:\Bitcoin\blockchain\blocks"
MAGIC = uint32(0xd9b4bef9)

class BlockCache(object):
    """ A block cache file (blkxxxxx.dat) containing saved block info. """
    def __init__(self, blk: int):
        self._file_id: int = blk
        self._filename: str = f'blk{str(blk).zfill(5)}.dat'
        self._dir:str = f'{BLOCK_DIR}\\'
        self._file = FileIO(f'{self._dir}{self._filename}', mode="r")
        self._reader = BufferedReader(self._file)
        self._reader.seek(0, 2)
        self._eof = self._reader.tell()
        self._reader.seek(0, 0)
        self._blocks = list()
        self._read_all_blocks()
    
    def _check_file(self) -> None:
        _magic: uint32 = pack_bytes(self._read(4), 32, False)
        if int(_magic) != int(MAGIC):
            raise Exception("Incorrect start value.")

    def _read_block(self) -> Dict:
        self._check_file()
        _block = {}
        _block["start_pos"]: int = self._reader.tell()
        _block["sz"]: uint32 = pack_bytes(self._read(4), 32, False)
        _cache_ = BytesIO(self._read(_block["sz"]))
        _cache = BufferedReader(_cache_, _block["sz"])
        _block["version"]: uint32 = pack_bytes(_cache.read(4), 32, False)
        _block["prevBlock"]: str = set_endian(_cache.read(32), 'big').hex()
        _block["merkleRoot"]: str = set_endian(_cache.read(32), 'big').hex()
        _block["time"]: int64 = int64(pack_bytes(_cache.read(4), 32, False))
        _block["bits"]: uint32 = pack_bytes(_cache.read(4), 32, False)
        _block["nonce"]: uint32 = pack_bytes(_cache.read(4), 32, False)
        _cache.seek(0, 0)
        _block["hash"]: str = sha256_2(_cache.read(80)).hex()
        _block["tx_sz"] = read_var_int(_cache)
        _block["tx"] = read_all_tx(_cache, _block["tx_sz"])
        _block["end_pos"]: int = self._reader.tell()
        return _block

    def _read_all_blocks(self) -> List:
        while self._reader.tell() < self._eof:
            self._blocks.append(self._read_block())

    def _read(self, sz: int) -> bytes:
        return self._reader.read(sz)

    def get_block_by_hash(self, hash: str):
        for _block in self._blocks:
            if _block["hash"] == hash:
                return _block
        raise ValueError("Hash not in file.")
