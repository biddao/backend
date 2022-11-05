from collections import defaultdict
from dataclasses import dataclass
from typing import List, Tuple

from crypto import generate_keypair, normalize
from contracts import DAODutchAuction
from client import web3
from web3.exceptions import ContractLogicError

# TODO: cache this, move somewhere else?
def auctioneers(contract_address):
    auctioneers = []
    index = 0
    while True:
        try:
            next_address = DAODutchAuction(contract_address).functions.auctioneers(index).call()
            index += 1
        except ContractLogicError:
            break
        auctioneers.append(next_address)

    return auctioneers


@dataclass
class EncryptedBid:
    bidder: str
    encrypted_bid_amount: int
    encrypted_max_price: int
    bidder_public_key: Tuple[int, int]


@dataclass
class RevealedBid:
    bidder: str
    max_price: int
    bid_amount: int


@dataclass
class RankedBidResult:
    ordered_bids: List[RevealedBid]
    realized_price: int
    total_bid: int


class Bidder:
    def __init__(self, account, contract_address):
        self.contract_address = contract_address
        self.locked_wei: int
        self.bid_amount: int
        self.max_price: int

        self.account = account

        priv_k, pub_k = generate_keypair()
        self.private_key: int = priv_k
        self.public_key: PointG1 = pub_k

    def get_sym_key(self):
        mpubk = self.get_master_public_key()
        sym_key = self.contract.functions.bn128_multiply([mpubk[0], mpubk[1], self.private_key]).call()[0]
        return sym_key

    def bid(self, bid_amount: int, max_price: int, locked_wei: int, skip_assertions=False):
        # Verify contract private key is valid, and extract that
        self.bid_amount = bid_amount
        self.max_price = max_price
        self.locked_wei = locked_wei

        if not skip_assertions:
            assert locked_wei <= web3.eth.get_balance(self.account.address)
            assert locked_wei >= bid_amount

        sym_key = self.get_sym_key()

        encrypted_bid_amount = self.contract.functions.encrypt(bid_amount, sym_key).call()
        encrypted_max_price = self.contract.functions.encrypt(max_price, sym_key).call()

        normal_pub_key = normalize(self.public_key)
        return self.contract.functions.bid(encrypted_bid_amount, encrypted_max_price, [int(normal_pub_key[0]), int(normal_pub_key[1])]).transact({"value": locked_wei, "from": self.account.address})

    def get_master_public_key(self) -> Tuple[int, int]:
        pub_key_count = self.contract.functions.publishedKeys().call()
        if pub_key_count != len(auctioneers(self.contract.address)):
            raise Exception("Master public key incomplete")
        pubk_x = self.contract.functions.masterPublicKey(0).call()
        pubk_y = self.contract.functions.masterPublicKey(1).call()
        return (pubk_x, pubk_y)


    @property
    def contract(self):
        return DAODutchAuction(self.contract_address)

    def withdraw():
        pass


def generate_bidders(contract_address, count) -> List[Bidder]:
    from accounts import get_account
    return [Bidder(get_account(i + 20), contract_address) for i in range(count)]


def get_all_bids(contract_address) -> List[EncryptedBid]:
    contract = DAODutchAuction(contract_address)
    filter_instance = contract.events.BidSubmitted.createFilter(fromBlock="0x0")
    print('filter_instance', filter_instance)
    results = []
    # look up each adress 
    bidders = set()
    for log in filter_instance.get_all_entries():
        bidders.add(log.args.bidder)


    for bidder in bidders:
        bid = contract.functions.bids(bidder).call()
        bidder_public_key = contract.functions.getBidderPublicKey(bidder).call()

        results.append(
            EncryptedBid(
                bidder,
                bid[1],
                bid[2],
                bidder_public_key,
            )
        )

    return results


def decrypt_bids(contract_address, auctioneer_priv_keys=None) -> List[RevealedBid]:
    encrypted_bids: List[EncryptedBid] = get_all_bids(contract_address)
    master_private_key = None

    contract = DAODutchAuction(contract_address)
    if not auctioneer_priv_keys:
        priv_key_count = contract.functions.revealedKeys().call()
        if priv_key_count != len(auctioneers(contract_address)):
            raise Exception("Cannot derive master secret key")
        master_private_key = contract.functions.masterSecretKey().call()
    else:
        # TODO: use specified private keys to generate master private key locally
        pass
    
    results = []
    for enc_bid in encrypted_bids:
        sym_key = contract.functions.bn128_multiply([enc_bid.bidder_public_key[0], enc_bid.bidder_public_key[1], master_private_key]).call()[0]
        bid_amount = contract.functions.decrypt(enc_bid.encrypted_bid_amount, sym_key).call()
        max_price = contract.functions.decrypt(enc_bid.encrypted_max_price, sym_key).call()

        results.append(RevealedBid(enc_bid.bidder, max_price, bid_amount))

    return results


def rank_bid_result(contract_address, bids: List[RevealedBid]) -> list[RevealedBid]:
    contract = DAODutchAuction(contract_address)
    bid_by_price = defaultdict(list)

    for bid in bids:
        bid_by_price[bid.max_price].append(bid)

    invalid_bids = []
    valid_bids = []

    # For each max_bid in reversed order
    for key in reversed(sorted(bid_by_price.keys())):
        # check if bid is valid
        for bid in reversed(sorted(bid_by_price[key], key=lambda x: bytes.fromhex(x.bidder[2:]))):
            lockedEth = contract.functions.lockedEth(bid.bidder).call()
            if lockedEth < bid.bid_amount:
                invalid_bids.append(bid)
            elif bid.bid_amount > bid.max_price:
                invalid_bids.append(bid)
            else:
                valid_bids.append(bid)


    last_max_price = 0
    total_bid = 0
    realized_max_price = 0

    for bid in valid_bids:
        print('bid max price', bid.max_price)
        print('bid amount', bid.bid_amount)

        if realized_max_price and bid.max_price != realized_max_price:
            break

        total_bid += bid.bid_amount

        if total_bid >= bid.max_price:
            realized_max_price = bid.max_price

    # If lowest max price not exceeded, total bid amount is realized
    if realized_max_price == 0:
        realized_max_price = total_bid

    ordered_bids = valid_bids + list(reversed(sorted(invalid_bids, key=lambda x: bytes.fromhex(x.bidder[2:]))))

    #bids_filled_at_price = total_bids_at_price - (total_bid - realized_max_price)
    return RankedBidResult(ordered_bids, realized_max_price, total_bid)
