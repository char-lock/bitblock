""" BitBlock v0.0.1 """

import asyncio
import sqlite3 as sql3
import threading
import time
from typing import Tuple, Optional

import nest_asyncio
nest_asyncio.apply()

from .rpc._types import *
from . import rpc

# Constants
GENESIS_BLOCK_HASH: BlockHash = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"

# Helper
def async_get(obj):
    _task = asyncio.create_task(obj)
    try:
        asyncio.get_running_loop().run_until_complete(_task)
    except RuntimeError:
        asyncio.new_event_loop().run_until_complete(_task)
    return _task.result()

def print_progress(
    job: str, 
    current: int, total: int, first: int,
    start: float, prev: float
):
    _percent: float = (current / total) * 100.00
    print(
        f"{job} [{'=' * int(_percent // 10)}"
        + f"{' ' * (10 - int(_percent // 10))}]"
        + f" {' ' if _percent < 10 else ''}{_percent:.2f}%"
        + f" ({current}/{total})"
        + f" avg. {(prev - start) / (current - first):.2f}s/block,"
        + f" est. {(total - current) * (prev - start) / (current - first):.2f}s"
        + f" remaining",
        end='\r'
    )

class BtcBlock(object):
    """ A block on the Bitcoin blockchain with a few methods that are easier
    to work with than the initial output from RPC.

    """
    __slots__ = ("_rpc_conn", "_block_hash", "_next_block_hash", 
        "_prev_block_hash", "_transactions", "_height", "_time")
    def __init__(self,
    rpc_conn: rpc.BitcoinRPC, block_hash: BlockHash):
        """ Initialises a BtcBlock. """
        self._rpc_conn: rpc.BitcoinRPC = rpc_conn
        self._block_hash: BlockHash = block_hash
        async_get(self._update_data())
    
    @classmethod
    def from_hash(cls,
        rpc_conn: rpc.BitcoinRPC, block_hash: BlockHash):
        """ Initialises a BtcBlock by its hash. """
        return cls(rpc_conn, block_hash)
    
    @classmethod
    async def from_height(cls,
        rpc_conn: rpc.BitcoinRPC, block_height: int):
        """ Initialises a BtcBlock by its height. """
        _block_hash: BlockHash = await rpc_conn.get_block_hash(block_height)
        return cls(rpc_conn, _block_hash)

    async def _update_data(self) -> None:
        """ Internal.
        
        Updates the information in the BtcBlock from the RPC.

        """
        _block: Block = await self._rpc_conn.get_block(
            block_hash = self._block_hash,
            verbosity = 2
        )
        self._height: int = _block["height"]
        try:
            self._next_block_hash: BlockHash = _block["nextblockhash"]
        except KeyError:
            self._next_block_hash: BlockHash = self._block_hash
        try:
            self._prev_block_hash: BlockHash = _block["previousblockhash"]
        except KeyError:
            self._prev_block_hash: BlockHash = self._block_hash
        self._time: float = _block["time"]
        self._transactions = await self._async_process_transactions(_block["tx"])
    
    async def _async_process_transactions(self,
        tx_list: List[RawTransaction]) -> List:
        """ Internal.

        Asynchroniously handles transactions.
        """
        _all_tx = []
        for _tx in tx_list:
            _tx = asyncio.create_task(self._async_interpret_transaction(_tx))
            _all_tx.append(
                await _tx
            )
        return _all_tx
            
    async def _async_interpret_transaction(self, _tx: RawTransaction):
        _tx_txid: str = _tx["txid"]
        _input = _tx["vin"]
        _tx_input: List = []
        _tx_output: List = []

        # Process the transaction inputs.
        for _i in _input:
            # Check whether or not the input is a coinbase.
            _coinbase = "coinbase" in _input[0].keys()
            # Check if there's an n value in this input.
            _n_exist = "n" in _input[0].keys()
            # Handle a coinbase transaction.
            if _coinbase:
                _tx_in_txid = _i["coinbase"]
                _tx_in_n: int = _i["sequence"]
                _tx_in_addr: List[str] = ["coinbase"]
                _tx_in_value: float = 50.00
            # Handle non-coinbase transaction.
            else:
                _tx_in_txid = _i["txid"]
                _tx_in_n: int = _i["n"] if _n_exist else 0
                # Pull the transaction from which this transaction originates.
                _input_tx = await self._rpc_conn.get_raw_transaction(
                    _tx_in_txid,
                    verbose = True
                )
                _in_vout = _input_tx["vout"][_tx_in_n]
                _in_spk = _in_vout["scriptPubKey"]
                if "addresses" in _in_spk.keys():
                    _tx_in_addr: List[str] = _in_spk["addresses"]
                else:
                    _tx_in_addr: List[str] = [_in_spk["hex"]]
                _tx_in_value: float = _in_vout["value"]
            # Append the input to the main input list.
            _tx_input.append((
                _tx_in_txid,
                _tx_in_n,
                _tx_in_addr,
                _tx_in_value,
            ))
        # Process transaction output
        for _o in _tx["vout"]:
            _out_spk = _o["scriptPubKey"]
            if "addresses" in _out_spk.keys():
                _tx_out_addr: List[str] = _out_spk["addresses"]
            else:
                _tx_out_addr: List[str] = [_out_spk["hex"]]
            _tx_out_value: float = _o["value"]
            _tx_output.append((
                _tx_out_addr,
                _tx_out_value,
            ))
        # Return the transaction.
        return [_tx_txid, _tx_input, _tx_output]
    
    def get_hash(self) -> BlockHash:
        """ Returns the block hash. """
        return self._block_hash
    
    def get_height(self) -> int:
        """ Returns the block height. """
        return self._height
    
    def get_next_hash(self) -> BlockHash:
        """ Returns the hash of the next block in the chain. """
        return self._next_block_hash
    
    def get_previous_hash(self) -> BlockHash:
        """ Returns the hash of the next block in the chain. """
        return self._prev_block_hash
    
    def get_transactions(self) -> List:
        """ Returns the list of transactions in this block. """
        return self._transactions

    def get_time(self) -> float:
        """ Returns the blocktime as UNIX epoch. """
        return self._time


class BitBlockCache(object):
    """ A SQLite3 database to store data from the Bitcoin blockchain with 
    information not readily available from the blockchain distilled for quick
    perusal.

    """
    __slots__ = ("_db_location", "_db", "_cursor")
    def __init__(self, db_location: str):
        self._db_location = db_location
        self._init_db()
    
    def _open(self) -> None:
        """ Internal.

        Connects to the cache database.

        """
        self._db = sql3.connect(self._db_location)
        self._cursor = self._db.cursor()
    
    def _save_and_close(self) -> None:
        """ Internal.

        Saves and closes the connection to the cache database.

        """
        if self._db:
            self._db.commit()
            self._db.close()
            self._cursor = None
            self._db = None
    
    def _close_no_save(self) -> None:
        """ Internal.

        Closes cache database connection without saving changes.

        """
        if self._db:
            self._db.close()
            self._cursor = None
            self._db = None
    
    def _init_db(self) -> None:
        """ Internal

        Checks for needed tables and adds them if not present.

        """
        self._open()
        _i_tx = not self.table_exists("transactions")
        _i_bal = not self.table_exists("balances")
        if _i_tx or _i_bal:
            if _i_tx:
                self._cursor.execute("""
                    CREATE TABLE transactions
                        (block_hash TEXT,
                         block_height NUMERIC,
                         txid TEXT,
                         txtime NUMERIC,
                         debit_txid TEXT,
                         debit_n NUMERIC,
                         debit_addresses TEXT,
                         debit_value NUMERIC,
                         credit_addresses TEXT,
                         credit_value NUMERIC
                        )
                """)
            if _i_bal:
                self._cursor.execute("""
                    CREATE TABLE balances
                        (addresses TEXT,
                         balance NUMERIC,
                         last_used NUMERIC
                        )
                """)
            self._save_and_close()
        return None
    
    def table_exists(self, table_name: str) -> bool:
        """ Returns whether or not `table_name` exists in the cache. """
        try:
            self._cursor.execute(f"SELECT * FROM {table_name}")
        except sql3.OperationalError:
            return False
        return True
    
    def cache_tx(
        self,
        tx: List,
        block_hash: str,
        block_height: int,
        block_time: int,
        ) -> None:
        """ Inserts `tx` into the cache database. """
        _txid: str = tx[0]
        _d_txid: str = tx[1][0][0]
        _d_n: int = tx[1][0][1]
        _d_addresses: str = ','.join(tx[1][0][2])
        _d_value: float = tx[1][0][3]
        _c_addresses: str = ','.join(tx[2][0][0])
        _c_value: float = tx[2][0][1]
        self._cursor.execute(f"""
            INSERT INTO transactions VALUES (
                "{block_hash}", "{block_height}",
                "{_txid}", {block_time},
                "{_d_txid}", {_d_n}, "{_d_addresses}", {_d_value},
                "{_c_addresses}", {_c_value}
            )
        """)
        self._db.commit()
    
    def cache_multi_tx(
        self,
        b_tx: List,
        block_hash: str,
        block_height: int,
        block_time: int
    ) -> None:
        """ Inserts all transactions in `tx` into the cache database. """
        self._open()
        for _t in b_tx:
            self.cache_tx(_t, block_hash, block_height, block_time)
        self._save_and_close()


class BitBlock(object):
    """ A representation of an RPC connection with a local cache of useful
    information derived from the blockchain.

    """
    __slots__ = ("_cache", "_rpc", "_block", "_auto_update", "_update_queue",
        "_threads")
    def __init__(self,
        rpc_username: str,
        rpc_password: str,
        rpc_url: str,
        db_location: str = ".\\.bitblock.cache.db",
        auto_update: bool = True):
        """ Initialises BitBlock """
        self._cache: BitBlockCache = BitBlockCache(db_location)
        self._rpc = rpc.BitcoinRPC(rpc_url, rpc_username, rpc_password)
        self._block = BtcBlock.from_hash(self._rpc, GENESIS_BLOCK_HASH)
        self._auto_update = auto_update
        self._update_queue = []
        self._threads = []
        async_get(self._update())

    async def _async_get_block(
        self,
        block_height) -> BtcBlock:
        """ Internal.

        Asynchroniously pulls block information from the RPC and returns it.

        """
        return async_get(BtcBlock.from_height(self._rpc, block_height))
        

    async def _cache_block_tx(self, block: BtcBlock):
        """ Internal.

        Asynchroniously process block transactions and write them to the cache.
        """
        self._cache.cache_multi_tx(block.get_transactions())

    async def _a_update(self, height: int):
        """ Internal.

        Individual async update processes.

        """
        _block = await self._async_get_block(height)
        self._update_queue.append( _block)
    
    def _process_updates(self):
        """ Internal.

        Clears out the update queue.

        """
        while len(self._update_queue) > 0:
            try:
                _block: BtcBlock = self._update_queue.pop(0)
                self._cache.cache_multi_tx(
                    _block.get_transactions(),
                    _block.get_hash(),
                    _block.get_height(),
                    _block.get_time()
                )
                with open('.bitblock.update', 'w+') as _f:
                    _f.write(str(_block.get_height()))
                    _f.close()
            except Exception:
                pass
        
    async def _threaded_block_pull(self, height: int) -> None:
        _thread = threading.Thread(target=self._a_update, args=(height,))
        _thread.start()
        self._threads.append(_thread)
        if len(self._threads) % 5 == 0:
            for thread in self._threads:
                thread.join()

    async def _update(self) -> None:
        """ Internal.

        Updates BitBlock as needed.

        """
        # Try to open the .bitblock.update and get the last processed block.
        _last_height: int = 0
        with open(".bitblock.update", "a+") as _f:
            _f.seek(0, 0)
            try:
                _last_height = int(_f.readlines()[0])
            except IndexError:
                pass
            _f.close()
        # Pull the current best block height.
        _best_hash: str = async_get(self._rpc.get_best_block_hash())
        _best_height: int = async_get(
            self._rpc.get_block(_best_hash)
        )["height"]
        _start_time = time.time()
        _last_time = time.time()
        _start_height = _last_height
        while _last_height < _best_height:
            await asyncio.create_task(self._a_update(_last_height))
            await asyncio.to_thread(self._process_updates)
            _last_height += 1

            print_progress(
                "pull block",
                _last_height, _best_height, _start_height,
                _start_time, _last_time
            )
            _last_time = time.time()
    
    def update_manual(self) -> None:
        """ Manually forces the cache to update itself. """
        _setting = self._auto_update
        self._auto_update = True
        self._update()
        self._auto_update = _setting