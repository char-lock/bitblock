""" bitblock._util

Provides utility functions and classes to the overall bitblock module.

"""

# Imports
import asyncio
import sqlite3 as sql3

from typing import Any, List
from types import FunctionType

from . import rpc
from .rpc._types import Block, BlockHash, RawTransaction


# Functions
def async_get(func: FunctionType) -> Any:
    """ Returns the results provided by the async function.

    This allows for an async coroutine to be called synchroniously.


    ### Parameters
    --------------

    func: FunctionType
        The async function to be ran synchroniously.


    ### Returns
    -----------

    Result of running `func`.

    """
    _task = asyncio.create_task(func)
    asyncio.get_running_loop().run_until_complete(_task)
    return _task.result()


def print_progress_update(
    label: str,
    start_value: int, current_value: int, target_value: int,
    proc_start_time: float, proc_current_time: float
):
    """ Prints a string to the console containing the information
    provided by a lengthy task.


    ### Parameters
    --------------

    label: str
        Label of the currently running process

    start_value: int
        Where the process started
    
    current_value: int
        Where in the process right now
    
    target_value: int
        Where the process needs to be

    proc_start_time: float
        Timestamp of when the process started

    proc_current_time: float
        Timestamp of right now
    

    ### Returns
    -----------

    Nothing -- generated string is printed to the console.

    """
    _quantity: int = target_value - start_value
    _processed: int = current_value - start_value
    _remaining: int = target_value - current_value

    _percent: float = current_value / _quantity * 100.00 if _quantity else 0
    
    _elapsed: float = proc_current_time - proc_start_time
    _time_per_value: float = _elapsed / _processed if _processed else 0
    _value_per_time: float = _processed / _elapsed if _elapsed else 0
    _eta_s: float = _time_per_value * _remaining
    _eta_m: float = _eta_s // 60
    _eta_h: float = _eta_m // 60
    _eta_m -= _eta_h * 60
    _eta_s -= _eta_h * 60 * 60
    _eta_s -= _eta_m * 60

    _bar_sz: int = int(_percent // 10.00)

    _text: str = (
        f"{label} [{'=' * _bar_sz}{' ' * (10 - _bar_sz)}]"
        + f" ({current_value}/{target_value})"
        + f" {_percent:.2f}%"
        + f" ({_value_per_time:.3f} bl/s) "
        + f" (est. {_eta_h:.0f}h {_eta_m:.0f}m {_eta_s:.2f}s remaining)"
    )
    _text += f"{(' ' * (120 - len(_text))) if len(_text) < 120 else ''}"
    print(_text, end="\r")


# Non-BitBlock Classes
class BtcBlock(object):
    """ A block on the Bitcoin blockchain.
    
    This is an incomplete implementation, as this is used for caching
    more than anything else.

    """
    __slots__ = (
        "_hash", "_height", "_rpc", "_next_hash", "_prev_hash", "_time",
        "_transactions",
    )

    def __init__(
        self,
        rpc_conn: rpc.BitcoinRPC,
        block_hash: BlockHash
    ):
        """ Initialises a BtcBlock.


        ### Parameters
        --------------
        
        rpc_conn: rpc.BitcoinRPC
            A connection to an RPC server
        
        block_hash: BlockHash
            Hash of the target block to load
        
        """
        self._rpc: rpc.BitcoinRPC = rpc_conn
        self._hash: BlockHash = block_hash
        async_get(self._update())
    

    @classmethod
    def from_hash(
        cls,
        rpc_conn: rpc.BitcoinRPC,
        block_hash: BlockHash
    ):
        """ Initialises a BtcBlock from a provided hash value.
        

        ### Parameters
        --------------
        
        rpc_conn: rpc.BitcoinRPC
            A connection to an RPC server
        
        block_hash: BlockHash
            Hash of the target block to load
        
        """
        return cls(rpc_conn, block_hash)
    

    @classmethod
    def from_height(
        cls,
        rpc_conn: rpc.BitcoinRPC,
        block_height: int
    ):
        """ Initialises a BtcBlock from a provided height value.
        
        
        ### Parameters
        --------------
        
        rpc_conn: rpc.BitcoinRPC
            A connection to an RPC server
        
        block_height: int
            Height of the target block to load

        """
        _hash: BlockHash = async_get(rpc_conn.get_block_hash(block_height))
        return cls(rpc_conn, _hash)
    

    @classmethod
    async def a_from_height(
        cls,
        rpc_conn: rpc.BitcoinRPC,
        block_height: int
    ):
        """ Initialises a BtcBlock from a provided height value.


        ### Parameters
        --------------

        rpc_conn: rpc.BitcoinRPC
            A connection to an RPC server
        
        block_height: int
            Height of the target block to load

        """
        _hash = await rpc_conn.get_block_hash(block_height)
        return cls(rpc_conn, _hash)
    

    async def _update(self) -> None:
        """ Internal ...

        Updates information of the BtcBlock from its RPC connection.

        """
        _block: Block = await self._rpc.get_block(
            block_hash = self._hash,
            verbosity = 2
        )
        self._height: int = _block["height"]
        # If this is the last block on the chain, it won't have a next
        # block listed. Rather than try to pull what the current best
        # height is, we can just try to nab the next value, and set it
        # to the current block if there isn't one.
        try:
            self._next_hash: BlockHash = _block["nextblockhash"]
        except KeyError:
            self._next_hash: BlockHash = self._hash
        # The same applies for the previous block hash, but for the
        # Genesis block of the chain.
        try:
            self._prev_hash: BlockHash = _block["previousblockhash"]
        except KeyError:
            self._prev_hash: BlockHash = self._hash
        self._time: float = _block["time"]
        # A separate function handles updating the class transactions
        # for readability's sake.
        self._transactions = await self._a_update_transactions(_block['tx'])

    async def _a_update_transactions(
        self,
        transactions: List[RawTransaction]
    ) -> List[List]:
        """ Internal ...

        Updates transaction information related to the BtcBlock.


        ### Parameters
        --------------

        transactions: List[RawTransaction]
            list containing the block's raw transaction information
        

        ### Returns
        -----------

        A far more legible and traversible list of transactions.

        """
        _all_tx: List[List] = []
        for _t in transactions:
            _tx = asyncio.create_task(self._a_process_transaction(_t))
            _all_tx.append( await _tx )
        return _all_tx

    
    async def _a_process_transaction(self, _t: RawTransaction) -> List:
        """ Internal ...

        Processes a single transaction into a legible format.

        
        ### Parameters
        --------------

        _t: RawTransaction
            transaction that needs to be processed.


        ### Returns
        -----------
        
        A list containing the transaction details.

        """
        _tx_txid: str = _t["txid"]
        _t_input: List = _t["vin"]
        _t_output: List = _t["vout"]
        _tx_input: List = []
        _tx_output: List = []
        # Process transaction input.
        for _i in _t_input:
            # Check whether or not the input is a coinbase.
            _coinbase = "coinbase" in _i.keys()
            # Check if there's an n value in this input.
            _n_exist = "n" in _i.keys()
            # Handle a coinbase transaction.
            if _coinbase:
                _tx_in_txid: str = _i["coinbase"]
                _tx_in_n: int = _i["sequence"]
                _tx_in_addr: List[str] = ["coinbase"]
                _tx_in_value: float = 50.00
            # Handle non-coinbase transaction.
            else:
                _tx_in_txid = _i["txid"]
                _tx_in_n: int = _i["n"] if _n_exist else 0
                # Pull the transaction from which this transaction
                # originates.
                _input_tx = await self._rpc.get_raw_transaction(
                    txid = _tx_in_txid,
                    verbose = True
                )
                # Pull the referred to vout that pays for this
                # transaction.
                _in_vout = _input_tx["vout"][_tx_in_n]
                _in_spk = _in_vout["scriptPubKey"]
                # This gives us the payer.
                if "addresses" in _in_spk.keys():
                    _tx_in_addr: List[str] = _in_spk["addresses"]
                else:
                    _tx_in_addr: List[str] = [_in_spk["hex"]]
                # And this ensures the in value.
                _tx_in_value: float = _in_vout["value"]
            # Finally, append the input information to the main input
            # list.
            _tx_input.append((
                _tx_in_txid,
                _tx_in_n,
                _tx_in_addr,
                _tx_in_value,
            ))
        # Process transaction output. It's much more straight forward.
        for _o in _t_output:
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
            

    @property
    def hash(self) -> BlockHash:
        """ Block hash of the current block. """
        return self._hash
    
    @property
    def height(self) -> int:
        """ Height of the current block. """
        return self._height
    
    @property
    def next_hash(self) -> BlockHash:
        """ Block hash of the next block in the chain.
        If there isn't a next block, the block hash of current block.

        """
        return self._next_hash
    
    @property
    def prev_hash(self) -> BlockHash:
        """ Block hash of the previous block in the chain.
        If there isn't a previuous block, the block hash of current block.

        """
        return self._prev_hash
    
    @property
    def transactions(self) -> List:
        """ List containing all transactions in this block in BitBlock
        format.

        """
        return self._transactions
    
    @property
    def time(self) -> float:
        """ Time block was generated as UNIX timestamp. """
        return self._time


class BitBlockCache(object):
    """ An SQLite3 database used to store data from the Bitcoin
    blockchain for BitBlock to pull at its leisure.

    """
    __slots__ = ("_filename", "_db", "_cursor")

    def __init__(self, db_location: str):
        """ Initialises the cache file.


        ### Parameters
        --------------
        db_location: str
            location where to store the cache file.
        
        """
        self._filename = db_location
        self._db = sql3.connect(self._filename)
        self._cursor = self._db.cursor()
        self._init_db()
    

    def open(self) -> None:
        """ Connects to the cache database. """
        self._db = sql3.connect(self._filename)
        self._cursor = self._db.cursor()
    

    def save_and_close(self) -> None:
        """ Closes the database connection after saving any changes to
        it.

        """
        if self._db:
            self._db.commit()
            self._db.close()


    def close_no_save(self) -> None:
        """ Closes the database connection and discards any changes. """
        if self._db:
            self._db.close()
    

    def _init_db(self) -> None:
        """ Internal ...

        Initialises database file by creating it if it doesn't exist,
        and adding any tables that are missing.

        """
        _i_tx: bool = not self.table_exists("transactions")
        _i_bal: bool = not self.table_exists("balances")
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
        self._db.commit()
    

    def table_exists(self, table_name: str) -> bool:
        """ Returns whether or not a table exists in the cache.

        
        ### Parameters
        --------------

        table_name: str
            name of the table to check for
        
        """
        try:
            self._cursor.execute(f"SELECT * FROM {table_name}")
        except sql3.OperationalError:
            return False
        return True
    
    def insert_transaction(
        self,
        tx: List,
        block_hash: BlockHash,
        block_height: int,
        block_time: float
    ) -> None:
        """ Inserts transaction into the cache database.


        ### Parameters
        --------------

        tx: List
            Transaction in BitBlock formatting
        
        block_hash: BlockHash
            Hash of block that holds this transaction
        
        block_height: int
            Height of block that holds this transaction
        
        block_time: float
            Time of block that holds this transaction
        
        """
        _txid: str = tx[0]
        _t_d_txid: List = []
        _t_d_n: List = []
        _t_d_addr: List = []
        _t_d_value: List = []
        _t_c_addr: List = []
        _t_c_value: List = []
        for _d in tx[1]:
            _t_d_txid.append(_d[0])
            _t_d_n.append(_d[1])
            _t_d_addr.append(_d[2])
            _t_d_value.append(_d[3])
        for _c in tx[2]:
            _t_c_addr.append(_c[0])
            _t_c_value.append(_c[1])
        for _i in range(len(tx[1])):
            self._cursor.execute(f"""
                INSERT INTO transactions VALUES (
                    "{block_hash}", "{block_height}",
                    "{_txid}", {block_time},
                    "{_t_d_txid[_i]}", {_t_d_n[_i]}, "{','.join(_t_d_addr[_i])}",
                    {_t_d_value[_i]}, "", 0
                )
            """)
        for _i in range(len(tx[2])):
            self._cursor.execute(f"""
                INSERT INTO transactions VALUES (
                    "{block_hash}", "{block_height}",
                    "{_txid}", {block_time},
                    "", 0, "", 0,
                    "{','.join(_t_c_addr[_i])}", {_t_c_value[_i]}
                )
            """)
        

    def insert_multiple_transactions(
        self,
        tx_list: List,
        block_hash: BlockHash,
        block_height: int,
        block_time: float
    ) -> None:
        """ Inserts all transactions provided into the cache database.
        

        ### Parameters
        --------------
        
        tx_list: List
            list of transactions to insert
        
        block_hash: BlockHash
            hash where transactions are located
        
        block_height: int
            height of block where transactions are located
        
        block_time: float
            time block was mined
        
        """
        self.open()
        for _t in tx_list:
            self.insert_transaction(
                _t,
                block_hash, block_height, block_time
            )
        self._db.commit()


    def fetch_unique_addresses(self, since: float = 0.00) -> List:
        """ Returns a list containing all of the unique addresses with
        related transactions that have been cached by BitBlock.


        ### Parameters
        --------------

        since: float
            time to grab unique addresses after

        """
        _addresses = []
        _addresses.extend(self._cursor.execute(f"""
            SELECT DISTINCT debit_addresses FROM transactions
                WHERE debit_addresses != "" AND txtime > {since}
        """))
        _addresses.extend(self._cursor.execute(f"""
            SELECT DISTINCT credit_addresses FROM transactions
                WHERE credit_addresses != "" AND txtime > {since}
        """))
        return list(set(_addresses))
    

    def get_address_balance(self, address: str, since: float = 0.00) -> float:
        """ Returns the calculated balance of an address from all
        cached transactions.


        ### Parameters
        --------------

        address: str
            address to pull balance for
        
        since: float
            time after to grab balance

        """
        _debits = sum(self._cursor.execute(f"""
            SELECT debit_value FROM transactions
                WHERE debit_addresses = {address} AND debit_value > 0
                    AND txtime > {since}
        """))
        _credits = sum(self._cursor.execute(f"""
            SELECT credit_value FROM transactions
                WHERE credit_addresses = {address} AND credit_value > 0
                    AND txtime > {since}
        """))
        return _credits - _debits
    

    def get_address_last_tx(self, address: str) -> float:
        """ Returns the time of the last cached transaction for an
        address.


        ### Parameters
        --------------

        address: str
            address to get last tx time

        """
        return max(self._cursor.execute(f"""
            SELECT txtime FROM transactions
                WHERE credit_addresses = {address} OR
                    debit_addresses = {address}
        """))
    

    def get_last_cached_time(self) -> float:
        """ Returns the latest time of cached transaction. """
        return max(self._cursor.execute(f"""
            SELECT txtime FROM transactions
        """))

    def get_last_balance_update_time(self) -> float:
        """ Returns the latest time of a cached balance. """
        return max(self._cursor.execute(f"""
            SELECT last_used FROM balances
        """))

    def get_address_cached_balance(self, address: str) -> float:
        """ Returns the last cached balance for an address.


        ### Parameters
        --------------

        address: str
            address to pull cached balance for

        """
        return max(self._cursor.execute(f"""
            SELECT balance FROM balances
                WHERE addresses = {address}
        """))
    
    def address_cached(self, address: str) -> str:
        """ Returns whether an address has ever had a balance cached.


        ### Parameters
        --------------

        address: str
            address to check for a record for

        """
        _entry = self._cursor.execute(f"""
            SELECT * FROM balances
                WHERE addresses = {address}
        """)
        return len(_entry) > 0

    def update_balance(
        self,
        address: str,
        balance: float,
        tx_time: float
    ) -> None:
        """ Updates the address's cached balance.
        

        ### Parameters
        --------------

        address: str
            address to update
        
        balance: float
            current balance of address
        
        tx_time: float
            last cached tx time

        """
        if self.address_cached(address):
            self._cursor.execute(f"""
                UPDATE balances
                    SET last_used = {tx_time}, balance = {balance}
                    WHERE addresses = {address}
            """)
        else:
            self._cursor.execute(f"""
                INSERT INTO balances VALUES(
                    "{address}", {balance}, {tx_time}
                )
            """)
        self._db.commit()
