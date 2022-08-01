""" bitblock.cache.parse

This BitBlock module handles caching data from the locally stored node
file. There are several classes here that assist in that process.

"""

from io import BufferedReader, BytesIO, FileIO

from os import pathsep
from typing import Dict, List

from ._util import *


class BlockDataReader(object):
    """ """
    def __init__(self, directory: str, blk_id: int = 0):
        """ Create a new reader for a locally-cached blk file using
        the given parent directory and file id.
        
        """
        self.parent_directory: str = directory
        if self.parent_directory[-1] != pathsep:
            self.parent_directory += pathsep
        self.file_id: int = blk_id
        self.filename: str = f"blk{str(blk_id).zfill(5)}.dat"
        self.path: str = f"{self.parent_directory}{self.filename}"
        self.file: FileIO = FileIO(self.path, mode="r")
        self._reader: BufferedReader = BufferedReader(self.file)
        # Pull the target file's size in bytes.
        self._reader.seek(0, 2)
        self.file_size: int = self._reader.tell()
        self._reader.seek(0, 0)
        self.index: List[Dict] = list()
        self._index_block_data()
        self.block_count: int = len(self.index)
    
    def _index_block_data(self) -> None:
        """ Fetches the index of blocks within the file and stores
        it in the index property.
        
        """
        self._reader.seek(0, 0)
        while self._reader.tell() < self.file_size:
            _ = read_uint32(self._reader)
            _block_size: uint32 = read_uint32(self._reader)
            _block_start: int = self._reader.tell()
            _block_hash: str = sha256_2(self._reader.read(80)).hex()
            self._reader.seek(_block_start, 0)
            _ = self._reader.read(_block_size)
            _block_end: int = self._reader.tell()
            self.index.append({
                "hash": _block_hash,
                "start": _block_start,
                "end": _block_end,
                "size": _block_size
            })
        self._reader.seek(0, 0)
    
    def get_block_by_index(self, index: int) -> "Block":
        """ Returns a Block cached in the current file according to
        the index of blocks stored in memory.
        
        """
        _entry: Dict = self.index[index]
        self._reader.seek(_entry["start"], 0)
        _raw_block: BytesIO = BytesIO(
            self._reader.read(_entry["size"])
        )
        self._reader.seek(0, 0)
        return Block(_raw_block)
    
    def get_block_index_by_hash(self, hash: str) -> int:
        """ Returns the index of a Block cached in the current file
        according to its hash.
        
        """
        for _i, _b in enumerate(self.index):
            if hash == _b["hash"]:
                return _i
        return -1
    
    def get_block_by_hash(self, hash: str) -> "Block":
        """ Returns a Block cached in the current file according
        to its hash.
        
        """
        _index: int = self.get_block_index_by_hash(hash)
        return self.get_block_by_index(_index)
    

class Block(object):
    """ """
    def __init__(self, raw_block: BytesIO):
        """ Creates a Block from the raw byte information. """
        self._reader = BufferedReader(raw_block)
        self.version: uint32 = read_uint32(self._reader)
        self.previous_block: str = read_hash256(self._reader)
        self.merkle_root: str = read_hash256(self._reader)
        self.time: uint32 = read_uint32(self._reader)
        self.bits: uint32 = read_uint32(self._reader)
        self.nonce: uint32 = read_uint32(self._reader)
        self._reader.seek(0, 0)
        self.hash: uint32 = sha256_2(self._reader.read(80)).hex()
        self.transaction_count: varint = read_varint(self._reader)
        self.transactions: List[Transaction] = list()
        for _i in range(self.transaction_count):
            self.transactions.append(Transaction(self._reader))


class Transaction(object):
    """ """
    def __init__(self, buffer: BufferedReader):
        """ Creates a Transaction from a buffered reader. """
        self.start_position: int = buffer.tell()
        self.version: uint32 = read_uint32(buffer)
        _return_position: int = buffer.tell()
        # Check whether this is a Segwit transaction.
        _marker: uint8 = read_uint8(buffer)
        _flag: uint8 = read_uint8(buffer)
        self.is_segwit = False
        if _marker != 0 or _flag != 1:
            buffer.seek(_return_position)
        else:
            self.is_segwit = True
        # Transaction :: Inputs
        _inputs_position: int = buffer.tell
        self.input_count: varint = read_varint(buffer)
        self.inputs: List[TransactionInput] = list()
        for _i in range(self.input_count):
            self.inputs.append(TransactionInput(buffer))
        # Transaction :: Outputs
        self.output_count: varint = read_varint(buffer)
        self.outputs: List[TransactionOutput] = list()
        for _i in range(self.output_count):
            self.outputs.append(TransactionOutput(buffer))
        _segwit_position: int = buffer.tell()
        if self.is_segwit:
            for _i in range(self.input_count):
                _num_op: varint = read_varint(buffer)
                for _n in range(_num_op):
                    _op: varint = read_varint(buffer)
                    _ = buffer.read(_op)
        _raw_lock_time: bytes = buffer.read(4)
        self.lock_time: uint32 = pack(_raw_lock_time, 32)
        _return_position = buffer.tell()
        buffer.seek(self.start_position)
        if self.is_segwit:
            _raw_version: bytes = buffer.read(4)
            _raw_in_out: bytes = buffer.read(
                _segwit_position - _inputs_position
            )
            _raw_bytes: bytes = (
                _raw_version + _raw_in_out + _raw_lock_time
            )
        else:
            _raw_bytes: bytes = buffer.read(
                _return_position - self.start_position
            )
        buffer.seek(_return_position)
        self.hash: str = sha256_2(_raw_bytes).hex()


class TransactionInput(object):
    """ """
    def __init__(self, buffer: BufferedReader):
        """ Creates a transaction input from a buffered reader. """
        self.hash: str = read_hash256(buffer)
        self.n: uint32 = read_uint32(buffer)
        self.script_size: varint = read_varint(buffer)
        # This is a hacky fix to handle whenever the script_sz is
        # greater than an index-ranged integer.
        _sig_script_buffer: List[str] = list()
        _script_sz: int = int(self.script_size)
        while _script_sz > 0:
            if _script_sz >= 0xffffffff:
                _script_sz -= 0xffffffff
                _sig_script_buffer.insert(
                    0,
                    set_endian(buffer.read(0xffffffff), 'big').hex()
                )
            else:
                _sig_script_buffer.insert(
                    0,
                    set_endian(buffer.read(_script_sz), 'big').hex()
                )
                _script_sz = 0
        self.sig_script: str = ''.join(_sig_script_buffer)
        self.sequence: uint32 = read_uint32(buffer)


class TransactionOutput(object):
    """ """
    def __init__(self, buffer: BufferedReader):
        """ Creates a transaction output from a buffered reader. """
        self.value: uint64 = read_uint64(buffer)
        self.script_size: varint = read_varint(buffer)
        # Similar hack as used in TransactionInput for a large 
        # script_size.
        _pk_script_buffer: List[str] = list()
        _script_sz: int = int(self.script_size)
        while _script_sz > 0:
            if _script_sz >= 0xffffffff:
                _script_sz -= 0xffffffff
                _pk_script_buffer.insert(
                    0,
                    set_endian(buffer.read(0xffffffff), 'big').hex()
                )
            else:
                _pk_script_buffer.insert(
                    0,
                    set_endian(buffer.read(_script_sz), 'big').hex()
                )
                _script_sz = 0
        self.pk_script: str = ''.join(_pk_script_buffer)
