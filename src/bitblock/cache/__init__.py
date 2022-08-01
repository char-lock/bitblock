""" bitblock.cache

This module handles the parsing and caching of local block files. It
allows for us to bypass the RPC connection for a far quicker polling
of blockchain data.

"""

from io import BufferedReader, BytesIO, FileIO
from numpy import uint8, uint16, uint32, uint64
from typing import List, TypeAlias, Union

from .util import *


BLOCK_MAGIC_NUMBER = uint32(0xd9b4bef9)


class BtcBlock(object):
    """ A block read from the local blockchain. """
    def __init__(self, raw_block: BytesIO):
        """ Initialises the BtcBlock.


        ### Parameters
        --------------

        raw_block: BytesIO
            the block to be processed

        file_id: int
            which file holds this block

        file_pos: int
            position in file where block is located

        block_height: int
            which block is being processed

        """
        self._raw: BytesIO = raw_block
        self._reader: BufferedReader = BufferedReader(self._raw)
        self._start_pos: int = self._reader.tell()
        self.block_sz: uint32 = read_uint32(self._reader)
        self.version: uint32 = read_uint32(self._reader)
        self.prev_block: str = set_endian(
            self._reader.read(32), 'big'
        ).hex()
        self.merkle_root: str = set_endian(
            self._reader.read(32), 'big'
        ).hex()
        self.time: uint32 = read_uint32(self._reader)
        self.bits: uint32 = read_uint32(self._reader)
        self.nonce: uint32 = read_uint32(self._reader)
        self._reader.seek(self._start_pos)
        self.hash: str = sha256_2(self._reader.read(80)).hex()
        self.tx_sz: varint = read_varint(self._reader)
        self.tx: List[BlockTx] = list()
        for _i in self.tx_sz:
            BlockTx(self._reader)
        self._ready = True


class BlockTx(object):
    """ Transaction within a block. """
    def __init__(self, block: BufferedReader):
        """ Initialises transaction.


        ### Parameters
        --------------

        block: BufferedReader
            block to read transaction from

        """
        self._start_pos: int = block.tell()
        self.version: uint32 = read_uint32(block)
        _return_pos: int = block.tell()
        # Check whether this is a Segwit transaction.
        _marker = read_uint8(block)
        _flag = read_uint8(block)
        _segwit = False
        if _marker != 0 or _flag != 1:
            block.seek(_return_pos)
        else:
            _segwit = True
        _tx_in_pos: int = block.tell()
        self.in_sz: varint = read_varint(block)
        # Transaction :: Inputs
        self.tx_in: List[BlockTxIn] = list()
        for _i in range(self.in_sz):
            self.tx_in.append(BlockTxIn(block))
        # Transaction :: Output
        self.out_sz: varint = read_varint(block)
        self.tx_out: List[BlockTxOut] = list()
        for _i in range(self.out_sz):
            self.tx_out.append(BlockTxOut(block))
        # Transaction :: Segwit
        _segwit_pos: int = block.tell()
        if _segwit:
            for _i in range(self.tx_in_sz):
                _num_op: varint = read_varint(block)
                for _n in range(_num_op):
                    _op: varint = read_varint(block)
                    _ = block.read(_op)
        _raw_lock_time = block.read(4)
        self.lock_time: uint32 = pack(_raw_lock_time, 32)
        _return_pos = block.tell()
        block.seek(self._start_pos)
        if _segwit:
            _raw_version: bytes = block.read(4)
            _raw_in_out: bytes = block.read(_segwit_pos - _tx_in_pos)
            _raw_bytes : bytes = _raw_version + _raw_in_out + _raw_lock_time
        else:
            _raw_bytes: bytes = block.read(_return_pos - self._start_pos)
        block.seek(_return_pos)
        self.hash: str = sha256_2(_raw_bytes).hex()


class BlockTxIn(object):
    """ Inputs for a transaction on the block. """
    def __init__(self, block: BufferedReader):
        """ Initialises a TxIn from the block.


        ### Parameters
        --------------

        block: BufferedReader
            block to read txin in

        """
        self.hash: str = set_endian(block.read(32), 'big').hex()
        self.n: uint32 = read_uint32(block)
        self.script_sz: varint = read_varint(block)
        # This is a hacky fix to handle whenever the script_sz is
        # greater than an index-ranged integer.
        _sig_script_buffer: List[str] = list()
        _script_sz_mutable: int = int(self.script_sz)
        while _script_sz_mutable > 0:
            if _script_sz_mutable >= 0xffffffff:
                _script_sz_mutable -= 0xffffffff
                _sig_script_buffer.insert(
                    0,
                    set_endian(block.read(0xffffffff), 'big').hex()
                )
            else:
                _sig_script_buffer.insert(
                    0,
                    set_endian(block.read(_script_sz_mutable), 'big').hex()
                )
                _script_sz_mutable = 0
        self.sig_script: str = ''.join(_sig_script_buffer)
        self.sequence: uint32 = read_uint32(block)


class BlockTxOut(object):
    """ Outputs for a transaction on the block. """
    def __init__(self, block: BufferedReader):
        """ Initialises TxOut from block.


        ### Parameters
        --------------

        block: BufferedReader
            block to pull txout from

        """
        self.value: uint64 = read_uint64(block)
        self.script_sz: varint = read_varint(block)
        # Similar hack as used for the BlockTxIn for a large script_sz
        _pk_script_buffer: List[str] = list()
        _script_sz_mutable = int(self.script_sz)
        while _script_sz_mutable > 0:
            if _script_sz_mutable >= 0xffffffff:
                _script_sz_mutable -= 0xffffffff
                _pk_script_buffer.insert(
                    0,
                    set_endian(block.read(0xffffffff), 'big').hex()
                )
            else:
                _pk_script_buffer.insert(
                    0,
                    set_endian(
                        block.read(_script_sz_mutable), 'big'
                    ).hex()
                )
                _script_sz_mutable = 0
        self.pk_script: str = ''.join(_pk_script_buffer)


class BlockReader(object):
    """ Reads data from a locally saved block file. """
    __slots__ = (
        "_dir", "_filename", "_file", "_reader", "_file_sz", "_blocks"
    )

    def __init__(self, dir: str):
        """ Initialises the BlockReader.


        ### Parameters
        --------------

        dir: str
            where the blk files are located

        """
        self._dir: str = dir
        self.filename: str = ''
        self._file: FileIO = None
        self._reader: BufferedReader = None
        self._file_sz: int = 0
        self.blocks: List[BtcBlock] = list()
        self.first_height: int = 0
        self.last_height: int = 0


    def set_block_file(self, id: int) -> None:
        """ Sets a target blk file as the current file.


        ### Parameters
        --------------

        id: int
            target blk id

        """
        self._last_height = 0
        self._filename = f'blk{str(id).zfill(5)}.dat'
        self._file = FileIO(self._file + self._filename)
        self._reader = BufferedReader(self._file)
        self._reader.seek(0, 2)
        self._file_sz = self._reader.tell()
        self._reader.seek(0, 0)


    def get_all_file_blocks(self) -> None:
        """ Puts all blocks in the current file into memory. """
        while self._reader.tell() < self._file_sz:
            _magic: uint32 = read_uint32(self._reader)
            if _magic != BLOCK_MAGIC_NUMBER:
                raise ValueError('Incorrect magic number.')
            _block_start: int = self._reader.tell()
            _block_sz: uint32 = read_uint32(self._reader)
            self._reader.seek(_block_start)
            _block = BytesIO(self._reader.read(_block_sz))
            self._blocks.append(BtcBlock(_block))
            self.last_height += 1


class BlockIndex(object):
    """ Index of blk files to blocks. """
    def __init__(self, dir: str):
        """ Initialises index.

        dir: str
            directory where blk files exist
        
        """
        self._dir = dir
        
