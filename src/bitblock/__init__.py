""" bitblock

This is the primary file for the bitblock module. It supplies
the bulk of the end-user-facing classes and functions.

 """

# Imports
import asyncio
import time

import nest_asyncio

from . import rpc
from ._util import *
from .rpc._types import *


# This is a quick fix for using multiple async loops. At some stage,
# this needs to be refactored out.
nest_asyncio.apply()


# Constants
GENESIS_BLOCK_HASH: BlockHash = (
    "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
)


# Main class
class BitBlock(object):
    """ Primary connection to the Bitcoin RPC and the BitBlock cache. """
    __slots__ = (
        "_cache", "_rpc", "_block", 
        "_auto_update", "_update_queue",
        "_update_thread_exists"
    )

    def __init__(self,
        rpc_username: str, rpc_password: str, rpc_url: str,
        db_location: str = ".\\.bitblock.cache.db",
        auto_update: bool = True
    ):
        """ Initialises BitBlock and begins the caching process. 
        
        
        ### Parameters
        --------------

        rpc_username: str
            username to connect to the RPC server
        
        rpc_password: str
            password to connect to the RPC server
        
        rpc_url: str
            url for the RPC server
        
        db_location: str
            where to save the bitblock cache ({DIR}\\.bitblock.cache.db)
        
        auto_update: bool
            whether BitBlock should immediately start updating its cache
        
        """
        self._cache: BitBlockCache = BitBlockCache(db_location)
        self._rpc = rpc.BitcoinRPC(rpc_url, rpc_username, rpc_password)
        self._block = BtcBlock.from_hash(self._rpc, GENESIS_BLOCK_HASH)
        self._auto_update = auto_update
        self._update_thread_exists = False
        self._update_queue = []
        async_get(self._a_update_tx())


    async def _a_queue_block_by_height(self, height: int):
        """ Internal ...

        Queues a block by its height.


        ### Parameters
        --------------

        height: int
            height of the block to queue

        """
        _b_coro = async_get(BtcBlock.a_from_height(self._rpc, height))
        self._update_queue.append(_b_coro)
    

    def _consume_update_queue(self):
        """ Internal ...

        Clears out the update queue.

        """
        if self._update_thread_exists:
            return None

        while len(self._update_queue) > 0:
            self._update_thread_exists = True
            _block: BtcBlock = self._update_queue.pop(0)
            self._cache.insert_multiple_transactions(
                _block.transactions,
                _block.hash,
                _block.height,
                _block.time
            )
            with open('.bitblock.update', 'w+') as _f:
                _f.write(str(_block.height))
                _f.close()
        self._update_thread_exists = False
        return None
        

    async def _a_update_tx(self) -> None:
        """ Internal ...

        Updates BitBlock as needed.

        """
        # If this is not set to autoupdate, stop.
        if not self._auto_update:
            return None
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
        # Log the time process started.
        _start_time = time.time()
        for _h in range(_last_height, _best_height + 1):
            _t = asyncio.create_task(self._a_queue_block_by_height(_h))
            await asyncio.gather(
                _t,
                asyncio.to_thread(self._consume_update_queue)
            )
            print_progress_update(
                "cache blocks",
                _last_height, _h, _best_height,
                _start_time, time.time()
            )
        while len(self._update_queue) > 0:
            print_progress_update(
                "cache tx",
                _last_height,
                _best_height - len(self._update_queue),
                _best_height,
                _start_time, time.time()
            )
    

    def _a_update_balances(self) -> None:
        """ Updates all balances from the transaction cache. """
        _last_tx_time: float = self._cache.get_last_cached_time()
        _last_balance_time: float = self._cache.get_last_balance_update_time()
        if _last_tx_time == _last_balance_time:
            return None
        _addresses: List = self._cache.fetch_unique_addresses(
            since=_last_balance_time
        )
        _total: int = len(_addresses)
        _done: int = 0
        _start: float = time.time()
        for _a in _addresses:
            _done += 1
            if self._cache.address_cached(_a):
                _balance: float = self._cache.get_address_cached_balance(_a)
            else:
                _balance: float = 0.00
            _balance += self._cache.get_address_balance(
                address = _a,
                since = _last_balance_time
            )
            _tx_time: float = self._cache.get_address_last_tx(_a)
            self._cache.update_balance(_a, _balance, _tx_time)
            print_progress_update(
                "cache balance",
                0, _total, _done,
                _start, time.time()
            )
            