""" BitBlock
    Copyright (C) 2022  C. Lockett

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

""" Custom types used throughout BitBlock to match the Bitcoin RPC
return style. These allow for better understanding of code throughout
the module, and a lot less confusion.

At least, for me.

"""

from typing import Any, Dict, List, TypeAlias, TypeVar, Union
from typing_extensions import Literal, TypedDict

BestBlockHash: TypeAlias = str
BlockHash: TypeAlias = str
BlockCount: TypeAlias = str
ConnectionCount: TypeAlias = int
Difficulty: TypeAlias = float
HelpText: TypeAlias = str
NetworkHashPS: TypeAlias = float

class MempoolInfo(TypedDict):
    """ Active state of the TX memory pool. 
    
    ### Properties
    --------------

    loaded: bool
        true if mempool is fully loaded

    size: int
        current tx count

    bytes: int
        sum of all virtual tx sizes

    usage: int
        total memory usage for the mempool

    maxmempool: int
        maximum memory usage for the mempool

    mempoolminfee: float
        minimum fee in BTC/kB for tx to be accepted

    minrelaytxfee: float
        current minimum relay fee for tx

    unbroadcastcount: int
        current number of tx w/o initial broadcast
    
    """

    loaded: bool
    size: int
    bytes: int
    usage: int
    maxmempool: int
    mempoolminfee: float
    minrelaytxfee: float
    unbroadcastcount: int


class _NetworkInfoNetworks(TypedDict):
    """ Information by network. Used by NetworkInfo.
    
    ### Properties
    --------------

    name: Literal['ipv4', 'ipv6', 'onion']
        network name

    limited: bool
        is the network limited using -onlynet?

    reachable: bool
        is the network reachable?

    proxy: str
        the proxy that is used for this network

    proxy_randomize_credentials: bool
        whether randomized credentials are used

    """
    name: Literal['ipv4', 'ipv6', 'onion']
    limited: bool
    reachable: bool
    proxy: str
    proxy_randomize_credentials: bool


class _NetworkInfoLocalAddresses(TypedDict):
    """ List of local addresses. Used by NetworkInfo.

    ### Properties
    --------------
    address: str
        network address

    port: int
        network port

    score: float
        relative score

    """
    address: str
    port: int
    score: float


class NetworkInfo(TypedDict):
    """ State info regarding P2P networking.

    ### Properties
    --------------

    version: int
        the server version

    subversion: str
        the server subversion string

    protocolversion: int
        the protocol version

    localservices: str
        the services we offer to the network in hex

    localservicesname: List[str]
        services we offer to the network

    localrelay: bool
        true if transaction relay is requested from peers

    timeoffset: int
        the time offset

    connections: int
        the total number of connections

    connections_in: int
        the number of inbound connections

    connections_out: int
        the number of outbound connections

    networkactive: bool
        whether p2p networking is enabled

    networks: List[_NetworkInfoNetworks]
        information per network

    relayfee: float
        minimum relay fee for tx in BTC/kB

    incrementalfee: float
        minimum fee increment for mempool limiting

    localaddresses: List[_NetworkInfoLocalAddresses]
        list of local addresses

    warnings: str
        any network and blockchain warnings

    """
    version: int
    subversion: str
    protocolversion: int
    localservices: str
    localservicesnames: List[str]
    localrelay: bool
    timeoffset: int
    connections: int
    connections_in: int
    connections_out: int
    networkactive: bool
    networks: List[_NetworkInfoNetworks]
    relayfee: float
    incrementalfee: float
    localaddresses: List[_NetworkInfoLocalAddresses]
    warnings: str


class _ChainTipsDetail(TypedDict):
    height: int
    hash: str
    branchlen: int
    status: Literal["active", "valid-fork", "valid-headers",
        "headers-only", "invalid"]


ChainTips = List[_ChainTipsDetail]


class _BlockHeader(TypedDict):
    hash: BlockHash
    confirmations: int
    height: int
    version: int
    versionHex: str
    merkleroot: str
    time: int
    mediantime: int
    nonce: int
    bits: str
    difficulty: float
    chainwork: str
    nTx: int
    previousblockhash: str
    nextblockhash: str


BlockHeader = Union[str, _BlockHeader]


class BlockStats(TypedDict):
    avgfee: int
    avgfeerate: int
    avgtxsize: int
    blockhash: str
    feerate_percentiles: List[int]
    height: int
    ins: int
    maxfee: int
    maxfeerate: int
    maxtxsize: int
    medianfee: int
    medintxsize: int
    minfee: int
    minfeerate: int
    mintxsize: int
    outs: int
    subsidy: int
    swtotal_size: int
    swtotal_weight: int
    swtxs: int
    time: int
    total_out: int
    total_size: int
    total_weights: int
    totalfee: int
    txs: int
    utxo_increase: int
    utxo_size_inc: int


class _RawTransactionVIn(TypedDict):
    txid: str
    vout: int
    scriptSig: Dict[str, str]
    sequence: int
    txinwitness: List[str]


class _RawTransactionScriptPubKey(TypedDict):
    asm: str
    hex: str
    reqSigs: int
    type: str
    addresses: List[str]


class _RawTransactionVOut(TypedDict):
    value: float
    n: int
    scriptPubKey: _RawTransactionScriptPubKey


class _RawTransaction(TypedDict):
    txid: str
    hash: str
    version: int
    size: int
    vsize: int
    weight: int
    locktime: int
    vin: List[_RawTransactionVIn]
    vout: List[_RawTransactionVOut]
    blockhash: str
    confirmations: int
    blocktime: int
    time: int


RawTransaction = Union[str, _RawTransaction]

class Block(_BlockHeader):
    strippedsize: int
    tx: List[RawTransaction]


class MiningInfo(TypedDict):
    blocks: int
    currentblockweight: int
    currentblocktx: int
    difficulty: float
    networkhashps: NetworkHashPS
    pooledtx: int
    chain: Literal["main", "test", "regtest"]
    warnings: str

BitcoinRPCResponse = TypeVar(
    "BitcoinRPCResponse",
    BestBlockHash,
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
)

class TransactionDebit(TypedDict):
    txid: str
    n: int
    addresses: List[str]
    value: float

class _TransactionCredit(TypedDict):
    addresses: List[str]
    value: float

TransactionCredit: TypeAlias = List[_TransactionCredit]

class Transactions(TypedDict):
    txid: str
    debit: TransactionDebit
    credits: TransactionCredit