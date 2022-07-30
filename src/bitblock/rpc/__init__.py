""" bitblock.rpc

Allows user to communicate with the RPC server with async.

"""

import itertools
from types import TracebackType
from typing import Any, List, Optional, Type, Union, Dict

import httpx
import orjson
from typing_extensions import Literal

from ._exceptions import ConfigurationError, RPCError
from ._types import (
    BestBlockHash,
    BitcoinRPCResponse,
    Block,
    BlockCount,
    BlockHash,
    BlockHeader,
    BlockStats,
    ChainTips,
    ConnectionCount,
    Difficulty,
    MempoolInfo,
    MiningInfo,
    NetworkHashPS,
    NetworkInfo,
    RawTransaction,
    HelpText
)

_next_rpc_id = itertools.count(1).__next__

class BitcoinRPC:
    """ Connection to the BitcoinRPC with async. """
    __slots__ = ("_url", "_client", "_max_retries")

    def __init__(self,
        url: str, rpc_user: str, rpc_password: str,
        max_retries: int = 5,
        **options: Any
    ) -> None:
        """ Initialises the Bitcoin RPC connection.


        ### Parameters
        --------------

        url: str
            url to the server

        rpc_user: str
            username to log into server

        rpc_password: str
            password to log into server

        max_retries: int
            how many retries before the client gives up

        """
        self._url = url
        self._max_retries = max_retries
        self._client = self._configure_client(rpc_user, rpc_password, **options)


    async def __aenter__(self) -> "BitcoinRPC":
        """ Async entry handler for BitcoinRPC. """
        return self


    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException, 
        exc_tb: TracebackType
    ) -> None:
        """ Async exit handler for BitcoinRPC. """
        await self.aclose()


    @staticmethod
    def _configure_client(
        rpc_user: str, rpc_password: str,
        **options: Any
    ) -> httpx.AsyncClient:
        """ Configure the `httpx.AsyncClient` for BitcoinRPC.


        ### Parameters
        --------------

        rpc_user: str
            username to connect to rpc.
        
        rpc_password: str
            password to connect to rpc.

        **options: Any
            httpx options for the AsyncClient.

        """
        auth = (rpc_user, rpc_password)
        headers = {"content-type": "application/json"}
        options = dict(options)
        if not options:
            return httpx.AsyncClient(auth=auth, headers=headers)
        if "auth" in options:
            raise ConfigurationError("`auth` set in options")
        if "headers" in options:
            _additional_headers = dict(options.pop("headers"))
            headers.update(_additional_headers)
            headers["content-type"] = "application/json"
        return httpx.AsyncClient(auth=auth, headers=headers, **options)


    @property
    def url(self) -> str:
        """ Current BitcoinRPC url. """
        return self._url


    @property
    def client(self) -> httpx.AsyncClient:
        """ Current BitcoinRPC client connection. """
        return self._client


    async def aclose(self) -> None:
        """ Closes the client connection with async. """
        await self.client.aclose()


    async def acall(
        self,
        method: str, 
        params: List[Union[str, int, List[str], None]],
        retry_sz: int = 0,
        **kwargs: Any
    ) -> BitcoinRPCResponse:
        """ Construct a custom async request from the Bitcoin RPC.


        ## Parameters
        -------------

        method: str
            RPC method to request.

        params: List
            parameters to pass alongside the method.

        retry_sz: int
            how many attempts have been tried so far.

        kwargs: Any
            any keyword arguments that need to be passed.

        """
        _retry_sz = retry_sz
        req = self.client.post(
            url=self.url, 
            content=orjson.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": _next_rpc_id(),
                    "method": method,
                    "params": params,
                }
            ),
            **kwargs
        )
        resp = orjson.loads((await req).content)
        if resp["error"] is not None:
            if _retry_sz < self._max_retries:
                return await self.acall(method, params, _retry_sz + 1, kwargs)
            else:
                raise RPCError(resp["error"]["code"], resp["error"]["message"])
        else:
            return resp["result"]


    async def get_best_block_hash(self) -> BestBlockHash:
        """ Returns the hash of the best (tip) block in the most-work
        fully-validated chain.

        """
        return await self.acall("getbestblockhash", [])


    async def get_block(
        self,
        block_hash: str, verbosity: Literal[0, 1, 2] = 1,
        timeout: Optional[float] = None
    ) -> Block:
        """ Return changes based upon verbosity setting.


        ### Parameters
        --------------

        block_hash: str
            hash of the target block

        verbosity: Literal[0, 1, 2]
            desired verbosity level

        timeout: Optional[float]
            how long before a request times out

        """
        return await self.acall(
            "getblock", [block_hash, verbosity],
            timeout=httpx.Timeout(timeout)
        )


    async def get_block_count(self) -> BlockCount:
        """ Returns the height of the most-work fully-validated chain. """
        return await self.acall("getblockcount", [])


    async def get_block_filter(
        self,
        block_hash: str, filtertype: Optional[str] = None
    ) -> Any:
        # TODO: Implement get_block_filter
        raise NotImplementedError("getblockfilter is not implemented.")


    async def get_block_hash(
        self,
        height: int,
        timeout: Optional[float] = None
    ) -> BlockHash:
        """ Returns hash of block in best-block-chain at height provided.


        ### Parameters
        --------------

        height: int
            height of desired block
        
        timeout: Optional[float]
            time before request times out
        
        """
        return await self.acall(
            "getblockhash", [height], timeout=httpx.Timeout(timeout)
        )


    async def get_block_header(
        self,
        block_hash: str, verbose: Optional[bool] = True,
        timeout: Optional[float] = None
    ) -> BlockHeader:
        """ Return block header with detail based upon verbosity setting.


        # Parameters

        block_hash: str
            desired block to grab header for
        
        verbose: bool
            whether to return more details or not

        timeout: Optional[float]
            how long before request times out

        """
        return await self.acall(
            "getblockheader", [block_hash, verbose], 
            timeout=httpx.Timeout(timeout)
        )


    async def get_block_stats(
        self,
        hash_or_height: Union[int, str], *stats: str,
        timeout: Optional[float] = None
    ) -> BlockStats:
        """ Compute per-block statistics for a given window. All
        amounts are in satoshis.


        ### Parameters
        --------------
        hash_or_height: Union[int, str]
            hash/height of desired block

        *stats: str
            desired block stats to receive

        timeout: Optional[float]
            time before request times out

        """
        return await self.acall(
            "getblockstats",
            [hash_or_height, list(stats) or None], 
            timeout=httpx.Timeout(timeout)
        )


    async def get_chain_tips(self) -> ChainTips:
        """ Return information about all known tips in the block tree, 
        including the main chain as well as orphaned branches.

        """
        return await self.acall("getchaintips", [])


    async def get_chain_tx_stats(
        self,
        nblocks: Optional[int], block_hash: Optional[str]
    ) -> Any:
        """ Compute statistics about the total number and rate of
        transactions in the chain.


        ### Parameters
        --------------

        nblocks: Optional[int]
            Size of the window in number of blocks

        block_hash: Optional[str]
            hash of the block that ends the window

        """
        # TODO: Implement get_chain_tx_stats
        raise NotImplementedError("getchaintxstats is not implemented.")


    async def get_difficulty(self) -> Difficulty:
        """ Returns the proof-of-work difficulty as a multiple of the 
        minimum difficulty.

        """
        return await self.acall("getdifficulty", [])


    async def get_mempool_ancestors(
        self,
        txid: str, 
        verbose: bool = False
    ) -> Any:
        """ If txid is in the mempool, returns all in-mempool ancestors.


        ### Parameters
        --------------

        txid: str
            transaction id to lookup

        verbose: bool
            True for a json object, False for array of ids

        """
        # TODO: Implement get_mempool_ancestors
        raise NotImplementedError("getmempoolancestors is not implemented.")


    async def get_mempool_descendants(
        self,
        txid: str, verbose: Optional[bool] = False
    ) -> Any:
        # TODO: Implement get_mempool_descendants
        raise NotImplementedError("getmempooldescendants is not implemented.")


    async def get_mempool_entry(self, txid: str) -> Any:
        # TODO: Implement get_mempool_entry
        raise NotImplementedError("getmempoolentry is not implemented.")


    async def get_mempool_info(self) -> MempoolInfo:
        """ Returns details on active state of the TX memory pool. """
        return await self.acall("getmempoolinfo", [])


    async def get_raw_mempool(self) -> Any:
        # TODO: Implement get_raw_mempool
        raise NotImplementedError("getrawmempool is not implemented.")


    async def get_tx_out(
        self,
        txid: str, n: int,
        include_mempool: Optional[bool] = True
    ) -> Any:
        """ Returns details about an unspent transaction output. """
        # TODO: Implement get_tx_out
        raise NotImplementedError("gettxout is not implemented.")


    async def get_tx_out_proof(
        self,
        txid: List[str], block_hash: Optional[str]
    ) -> Any:
        # TODO: Implement get_tx_out_proof
        raise NotImplementedError("gettxoutproof is not implemented.")


    async def get_tx_out_set_info(self, 
        hash_type: Optional[Literal[
            "hash_serialized_2", "none"
        ]] = "hash_serialized_2"
    ) -> Any:
        # TODO: Implement get_tx_out_set_info
        raise NotImplementedError("gettxoutsetinfo is not implemented.")


    async def precious_block(self, block_hash: str) -> None:
        """ Treats a block as if it were received before others with 
        the same work.

        """
        await self.acall("preciousblock", [block_hash])


    async def prune_blockchain(self, height: int) -> int:
        """ Prunes the blockchain to the provided height. Returns the 
        height of the last block pruned.

        """
        return await self.acall("pruneblockchain" [height])


    async def save_mempool(self) -> None:
        """ Dumps the mempool to disk. It will fail until the previous 
        dump is fully loaded.

        """
        await self.acall("savemempool", [])


    async def verify_chain(self,
        check_level: Optional[Literal[0, 1, 2, 3, 4]] = 3,
        n_blocks: Optional[int] = 6
    ) -> bool:
        """ Verifies blockchain database. """
        return await self.acall("verifychain", [check_level, n_blocks])


    async def verify_tx_out_proof(self, proof: str) -> List[str]:
        """ Verifies that a proof points to a transaction in a block, 
        returning the transaction it commits to and throwing an RPC 
        error if the block is not in our best chain


        ### Parameters
        -------------

        proof: str
            hex-encoded proof generated by getrxoutproof

        """
        return await self.acall("verifytxoutproof", [proof])


    async def get_memory_info(self,
        mode: Optional[Literal["stats", "mallocinfo"]] = "stats"
    ) -> Any:
        # TODO: Implement get_memory_info
        raise NotImplementedError("getmemoryinfo is not implemented.")


    async def get_rpc_info(self) -> Any:
        # TODO: Implement get_rpc_info
        raise NotImplementedError("getrpcinfo is not implemented.")


    async def help(self, command: Optional[str] = None) -> HelpText:
        """ List all commands, or get help for a specified command. """
        return await self.acall("help", [command])


    async def logging(
        self,
        include: Optional[List[str]] = None, 
        exclude: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """ Gets and sets the logging configuration. """
        return await self.acall(
            "logging",
            [list(include) or None, list(exclude) or None]
        )


    async def stop(self) -> Literal["Bitcoin Core stopping"]:
        """ Request a graceful shutdown of Bitcoin Core. """
        return await self.acall("stop", [])


    async def uptime(self) -> int:
        """ Returns the total uptime of the server. """
        return await self.acall("uptime", [])
    
    async def generate_block(
        self,
        output: str, rawtx_or_txid: List[str]
    ) -> BlockHash:
        """ Mine a block with a set of ordered transactions immediately 
        to a specified address or descriptor (before the RPC call 
        returns)

        """
        return await self.acall("generateblock", [])


    async def generate_to_address(
        self, n_blocks: int,
        address: str, maxtries: Optional[int] = 1000000
    ) -> List[BlockHash]:
        """ Mine blocks immediately to a specified address (before the 
        RPC call returns)

        ### Parameters
        --------------

        n_blocks: int
            

        """
        return await self.acall(
            "generatetoaddress", [n_blocks, address, maxtries]
        )


    async def generate_to_descriptor(
        self,
        num_blocks: int, descriptor: str,
        maxtries: Optional[int] = 1000000
    ) -> List[BlockHash]:
        """ Mine blocks immediately to a specified descriptor (before 
        the RPC call returns)

        """
        return await self.acall(
            "generatetodescriptor",
            [num_blocks, descriptor, maxtries]
        )


    async def get_block_template(self, template_request: Any) -> Any:
        # TODO: Implement get_block_template
        raise NotImplementedError("getblocktemplate is not implented.")


    async def get_mining_info(self) -> MiningInfo:
        """ Returns an object containing mining-related information """
        return await self.acall("getmininginfo", [])


    async def get_network_hash_ps(
        self,
        nblocks: Optional[int] = 120,
        height: Optional[int] = -1
    ) -> NetworkHashPS:
        """ Returns the estimated network hashes per second based on 
        the last n blocks.

        """
        return await self.acall("getnetworkhashps", [nblocks, height])


    async def prioritise_transaction(
        self,
        txid: str, fee_delta: int
    ) -> Literal[True]:
        """ Accepts the transaction into mined blocks at a higher (or 
        lower) priority.

        """
        return await self.acall("prioritisetransaction", [txid, 0, fee_delta])


    async def get_raw_transaction(
        self,
        txid: str, verbose: Optional[bool] = False,
        block_hash: Optional[str] = None
    ) -> RawTransaction:
        """ Return the raw transaction data. 
        
        ### Parameters
        --------------

        txid: str
            txid for which to pull data.
        
        verbose: Optional[bool]
            whether to provide more or less detail.

        block_hash: Optional[str]
            

        """
        return await self.acall("getrawtransaction", [txid, verbose, block_hash])


    async def get_network_info(self) -> NetworkInfo:
        """ Returns an object containing various state info regarding 
        P2P networking.

        """
        return await self.acall("getnetworkinfo", [])


    async def get_connection_count(self) -> ConnectionCount:
        """ Returns the number of connections to other nodes. """
        return await self.acall("getconnectioncount", [])
