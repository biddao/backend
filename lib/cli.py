import click
from crypto import normalize, generate_keypair

from accounts import get_account
from contracts import DAODutchAuction, TestERC20
from client import web3
from bidder import Bidder, get_all_bids, decrypt_bids, rank_bid_result

import os
keys_dir = os.path.dirname(__file__)
relative_path = "../keys/"
full_path = os.path.join(keys_dir, relative_path)

@click.group()
def cli():
    pass

def commit(deployed_auction, address, priv_pub):
    # generate keypair
    if priv_pub == None:
        priv_pub = {'priv': None, 'pub': None}
        priv_pub['priv'], priv_pub['pub'] = generate_keypair()

        # store keypair
        relative_path = "../keys/" + address + ".txt"
        full_path = os.path.join(keys_dir, relative_path)
        with open(full_path, 'w') as f:
            f.write(priv_pub['priv'] + '\n' + priv_pub['pub'])

    npk = list(normalize(priv_pub['pub']))

    # deploy on chain
    index = deployed_auction.indexOfAuctioneers(address).call()
    deployed_auction.setPublicKey(index, [int(npk[0]), int(npk[1])], {"from": address})

    return

def reveal(deployed_auction, address, priv_pub):
    # fetch keypair if not given
    if priv_pub == None:
        priv_pub = {'priv': None, 'pub': None}

        relative_path = "../keys/" + address + ".txt"
        full_path = os.path.join(keys_dir, relative_path)
        with open(full_path) as f:
            lines = f.readlines()
            priv_pub['priv'] = lines[0].rstrip()
            priv_pub['pub'] = lines[1].rstrip()

    index = deployed_auction.indexOfAuctioneers(address).call()
    deployed_auction.revealPrivateKey(index, priv_pub['priv'], {"from": address})
    return

@cli.command()
@click.argument("contract_address")
@click.argument("endpoint")
@click.argument("address")
@click.option("-pr", "--privatekey", "private_key")
@click.option("-pu", "--publickey", "public_key")
def execute(contract_address, endpoint, address, private_key, public_key):
    deployed_auction = DAODutchAuction(contract_address)
    priv_pub = {'priv': private_key, 'pub': public_key}
    if endpoint == 'commit':
        commit(deployed_auction, address, priv_pub)
    else:
        reveal(deployed_auction, address, priv_pub)


@cli.command()
def solve():
    contract_address = load_contract_address()
    deployed_auction = DAODutchAuction(contract_address)
    # deployed_auction.revealAllBids(addresses)


@cli.command()
def get_bids():
    contract_address = load_contract_address()
    enc_bids = get_all_bids(contract_address)
    for index, bid in enumerate(enc_bids):
        print(f"Bid #{index}:")
        print(f"Bidder: {bid.bidder}")
        print(f"Encrypted bid amount {bid.encrypted_bid_amount}")
        print(f"Encrypted max price {bid.encrypted_max_price}")
        print(f"Public key {bid.bidder_public_key}\n")

    deployed_auction = DAODutchAuction(contract_address)

    # Assume all keys are revealed here
    if deployed_auction.functions.revealedKeys().call() == 0:
        print("Master private key not yet revealed...")
        return

    click.confirm("Master private key has been revealed... decrypt the bids?")
    
    # deployed_auction.revealAllBids(addresses)
    dec_bids = decrypt_bids(contract_address)

    for index, bid in enumerate(dec_bids):
        print(f"Bid #{index}:")
        print(f"Bidder: {bid.bidder}")
        dec_bid_amount_eth = web3.fromWei(bid.bid_amount, "ether")
        print(f"Bid amount {dec_bid_amount_eth} ETH")
        dec_max_price_eth = web3.fromWei(bid.max_price, "ether")
        print(f"Max price {dec_max_price_eth}\n")

    click.confirm("Publish results of auction?")

    ranked_results = rank_bid_result(contract_address, dec_bids)
    ordered_addrs = [bid.bidder for bid in ranked_results.ordered_bids]

    sender_account = get_account(0)
    deployed_auction.functions.revealAllBids(ordered_addrs).transact({"from": sender_account.address})

    print("\nAuction results")
    results = deployed_auction.functions.results(sender_account.address).call()
    realized_price_eth = web3.fromWei(results[0], "ether") 
    included_bid_amount = web3.fromWei(results[1], "ether") 
    print(f"Realized price: {realized_price_eth} ETH")
    print(f"Included bids: {included_bid_amount} ETH")


@cli.command()
@click.argument("address")
def withdraw(address):
    sender = get_account(99)
    contract_address = load_contract_address()
    deployed_contract = DAODutchAuction(contract_address)

    click.prompt(f"Withdrawing funds for {address}. Continue?")
    current_balance = web3.eth.get_balance(address)
    locked_wei = deployed_contract.functions.lockedEth(address).call()
    locked_eth = web3.fromWei(locked_wei, "ether")
    print(f"Locked eth {locked_eth}")
    deployed_contract.functions.withdrawTo(address).transact({"from": sender.address})
    new_balance = web3.eth.get_balance(address)
    delta_balance_eth = web3.fromWei(new_balance - current_balance, "ether")

    print(f"Refunded {delta_balance_eth} ETH")

    vote_token_address = deployed_contract.functions.votesToken().call()
    deployed_erc20 = TestERC20(vote_token_address)
    token_balance = deployed_erc20.functions.balanceOf(address).call()
    token_balance_eth = web3.fromWei(token_balance, "ether")

    print(f"Rewarded {token_balance_eth} ETH worth of voting tokens")



@cli.command()
@click.argument("auctioneer_count")
def deploy(auctioneer_count):
    auctioneers = []
    for i in range(int(auctioneer_count)):
        auctioneers.append(get_account(i).address)
    auctioneers = sorted(auctioneers, key=lambda x: bytes.fromhex(x[2:]))

    for i, auctioneer in enumerate(auctioneers):
        print(f"Auctioneer #{i}: {auctioneer}")

    timestamp = web3.eth.getBlock("latest").timestamp
    expiration = timestamp + 60 * 60 * 24

    deployed_auction_tx = DAODutchAuction.constructor(auctioneers, expiration).transact({'from': auctioneers[0]})
    contract_address = web3.eth.getTransactionReceipt(deployed_auction_tx)["contractAddress"]

    with open("./contract-address.txt", "w") as f:
        f.write(f"{contract_address}\n")

    deployed_auction = DAODutchAuction(contract_address)

    print(f"Deployed DAO Dutch Auction to {contract_address}")

    click.confirm("Do you want to continue?")

    print(f"Generating keys for auctioneers")

    auctioneer_keys = {}

    for auctioneer in auctioneers:
        priv, pub = generate_keypair()
        auctioneer_keys[auctioneer] = {
            "priv": priv,
            "pub": pub
        }

        index = int(deployed_auction.functions.getIndex(auctioneer).call())
        npk = normalize(pub)
        print(f"Public key for {auctioneer}: {npk}\n")
        deployed_auction.functions.setPublicKey(index, [int(npk[0]), int(npk[1])]).transact({"from": auctioneer})

    print(f"Bidding is open")
    click.confirm("Do you want to reveal auctioneer private keys?")

    for auctioneer in auctioneers:
        index = int(deployed_auction.functions.getIndex(auctioneer).call())
        key = auctioneer_keys[auctioneer]["priv"]
        print(f"Secret key for {auctioneer}: {key}\n")
        deployed_auction.functions.revealPrivateKey(index, key).transact({"from": auctioneer})

@cli.command()
def autobid():
    contract_address = load_contract_address()

    with open("preset-bids.txt") as f:
        bidlines = f.readlines()

    print(f"Loaded {len(bidlines)} preset bids")

    for index, bidline in enumerate(bidlines):
        bid_data = [bid.strip() for bid in bidline.split(",")]
        account = get_account(index)
        place_bid(contract_address, account, bid_data[0], bid_data[1], bid_data[2])


def place_bid(contract_address, account, bid_amount_eth, max_price_eth, send_eth):
    bid_amount = web3.toWei(bid_amount_eth, "ether")
    max_price = web3.toWei(max_price_eth, "ether")
    send_wei = web3.toWei(send_eth, "ether")

    bidder = Bidder(account, contract_address)

    print(f"New bidder {account.address} with public key: {normalize(bidder.public_key)}\n")

    print(f"Max price:   {max_price_eth} ETH")
    print(f"Bid amount:  {bid_amount_eth} ETH")
    print(f"ETH to send: {send_eth} ETH")
    click.confirm("Ready to place bid?")
    bidder.bid(bid_amount, max_price, send_wei)
    print(f"Bid sucessful")

    bid_data = bidder.contract.functions.bids(account.address).call()
    print(f"Encrypted bid amount: {bid_data[1]}")
    print(f"Encrypted max price:  {bid_data[2]}")


@cli.command()
@click.argument("account_index")
@click.argument("bid_amount_eth")
@click.argument("max_price_eth")
@click.argument("send_eth")
def bid(account_index, bid_amount_eth, max_price_eth, send_eth):
    account = get_account(int(account_index))
    contract_address = load_contract_address()
    place_bid(contract_address, account, bid_amount_eth, max_price_eth, send_eth)


def load_contract_address() -> str:
    contract_address = None
    with open("./contract-address.txt") as f:
        contract_address = f.readlines()[0].rstrip()

    if not contract_address:
        raise Exception("Contract not found")

    print(f"Found contract at: {contract_address}")
    return contract_address


if __name__ == "__main__":
    cli()
