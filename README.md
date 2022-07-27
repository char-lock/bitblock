# BitBlock
### A Bitcoin RPC module for Python with a little bit extra.

## Purpose
This Python module is intended to allow a developer to be able to interact with
less obvious information available from the Bitcoin blockchain.

## How Does It Work
Information like transactions and address balances are available from a locally
created database that caches information from the blockchain. This cache is
persistent, but can be removed by the user and reinitialised at any time
if it is believed to be consuming too much space.

## But Why?
For a truly decentralized network, it is not enough that users
*can* access information at their own leisure, instead it must be readily
available and easy to implement from any client. While I admit that storage-
space is a concern, it would be a concern regardless. And once the blockchain
has been cached by BitBlock, it is no longer necessary for a user to maintain
their own blockchain copy, as the useful information has been distilled.

## License
This software is released under the GNU General Public License. Please
see the LICENSE for more details.