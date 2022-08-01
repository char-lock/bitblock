""" bitblock.cache

This BitBlock module handles caching data from the locally stored
node file.

"""

import sqlite3 as sql3

from os import walk, curdir

from .parse import *


class BlockCache(object):
    """ """
    def __int___(self):
        """ Initialises the BitBlock cache. """
        self.parent_directory: str = curdir
        if self.parent_directory[-1] != pathsep:
            self.parent_directory += pathsep
        self.filename: str = ".bitblock.cache"
        self.file_path: str = f"{self.parent_directory}{self.filename}"
        self._db: sql3.Connection = sql3.connect(self.file_path)
        self._cursor: sql3.Cursor = self._db.cursor()
        self._init_db()
    
    def _create_table(self, table: str, definitions: Dict) -> None:
        """ Creates a table based upon the provided dictionary. """
        _command: str = f"CREATE TABLE {table} ("
        for k, v in definitions:
            _command += f"{k} {v},"
        _command[-1] = ")"
        self._cursor.execute(_command)
        self._db.commit()
    
    def _table_exists(self, table: str) -> bool:
        """ Returns whether or not a table exists. """
        try:
            self._cursor.execute(f"SELECT * FROM {table}")
        except sql3.OperationalError:
            return False
        return True
    
    def _insert_values(self, table: str, values: List) -> None:
        """ Inserts the provided values into the given table. """
        _command: str = f"INSERT INTO {table} VALUES ("
        for _v in values:
            _command += f"{_v},"
        _command[-1] = ")"
        self._cursor.execute(_command)
        self._db.commit()
    
    def _init_db(self) -> None:
        _i_tx: bool = not self.table_exists("transactions")
        _i_index: bool = not self.table_exists("block_index")
        _i_balances: bool = not self.table_exists("balances")
        _tx: Dict = {
            "block_hash": "TEXT",
            "block_height": "NUMERIC",
            "txid": "TEXT",
            "txtime": "NUMERIC",
            "debit_ref_txid": "TEXT",
            "debit_ref_n": "NUMERIC",
            "debit_addresses": "TEXT",
            "debit_value": "NUMERIC",
            "credit_n": "NUMERIC",
            "credit_addresses": "TEXT",
            "credit_value": "TEXT"
        }
        _index: Dict = {
            "block_hash": "TEXT",
            "block_height": "NUMERIC",
            "block_file": "TEXT",
            "file_position": "TEXT"
        }
        _balances: Dict = {
            "addresses": "TEXT",
            "balance": "NUMERIC",
            "last_used": "NUMERIC"
        }
        if _i_tx: self._create_table("transactions", _tx)
        if _i_index: self._create_table("block_index", _index)
        if _i_balances: self._create_table("balances", _balances)


class Bitblock(object):
    """ """
    def __init__(self, directory: str):
        self.parent_directory: str = directory
        self.last_id: int = self._find_last_id()
        self.last_hash: str = BlockDataReader(
            self.parent_directory, 
            self.last_id
        ).index[-1]["hash"]
    
    def _find_last_id(self) -> int:
        """ Returns the last blk file available in the parent
        directory.
        
        """
        _last: int = 0
        for _f in walk(self.parent_directory)[2]:
            if _f.find("blk") > -1:
                _id: int = _f[3:-4]
                _last = _id if _id > _last else _last
        return _last
    