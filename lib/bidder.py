from typing import List, Tuple

from crypto import generate_keypair, normalize
from contracts import DAODutchAuction
from client import web3
from web3.exceptions import ContractLogicError


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

    def bid(self, bid_amount: int, max_price: int, locked_wei: int):
        # Verify contract private key is valid, and extract that
        self.bid_amount = bid_amount
        self.max_price = max_price
        self.locked_wei = locked_wei
        assert locked_wei <= web3.eth.get_balance(self.account.address)
        assert locked_wei >= bid_amount

        sym_key = self.get_sym_key()

        encrypted_bid_amount = self.contract.functions.encrypt(bid_amount, sym_key).call()
        encrypted_max_price = self.contract.functions.encrypt(max_price, sym_key).call()

        normal_pub_key = normalize(self.public_key)
        return self.contract.functions.bid(encrypted_bid_amount, encrypted_max_price, [int(normal_pub_key[0]), int(normal_pub_key[1])]).transact({"value": locked_wei, "from": self.account.address})

    def get_master_public_key(self) -> Tuple[int, int]:
        pub_key_count = self.contract.functions.publishedKeys().call()
        if pub_key_count != len(self.auctioneers()):
            raise Exception("Master public key incomplete")
        pubk_x = self.contract.functions.masterPublicKey(0).call()
        pubk_y = self.contract.functions.masterPublicKey(1).call()
        return (pubk_x, pubk_y)

    # TODO: cache this
    def auctioneers(self):
        auctioneers = []
        index = 0
        while True:
            try:
                next_address = self.contract.functions.auctioneers(index).call()
                index += 1
            except ContractLogicError:
                break
            auctioneers.append(next_address)

        return auctioneers

    @property
    def contract(self):
        return DAODutchAuction(self.contract_address)

    def withdraw():
        pass


def generate_bidders(contract_address, count) -> List[Bidder]:
    from accounts import get_account
    return [Bidder(get_account(i), contract_address) for i in range(count)]
