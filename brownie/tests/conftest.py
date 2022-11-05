import pytest

from dataclasses import dataclass
from typing import List

from brownie import (
    accounts,
    BN128,
    DAODutchAuction,
    Encryption,
    web3,
)
from brownie.network import priority_fee, max_fee

from crypto import generate_keypair, PointG1


NUM_AUCTIONEERS = 4



@dataclass
class Auctioneer:
    index: int
    address: str
    public_key: PointG1
    private_key: int

    def __init__(self, eth_address, index):
        self.address = eth_address
        self.index = index
        self.private_key, self.public_key = generate_keypair()


@pytest.fixture(scope="session", autouse=True)
def set_fee():
    priority_fee("2 gwei")
    max_fee("2 gwei")


@pytest.fixture()
def admin():
    return accounts[0]


@pytest.fixture()
def auctioneers() -> List[Auctioneer]:
    sorted_addresses = sorted([account.address for account in accounts[1:NUM_AUCTIONEERS+1]])

    return [
        Auctioneer(address, index)
        for index, address in enumerate(sorted_addresses)
    ]


@pytest.fixture()
def expiration():
    return int(web3.eth.getBlock('latest')['timestamp']) + 60 * 60 * 100


@pytest.fixture()
def dao_dutch_auction(admin, auctioneers, expiration):
    return admin.deploy(DAODutchAuction, [x.address for x in auctioneers], expiration)
