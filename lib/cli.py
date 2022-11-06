import click
from crypto import normalize, generate_keypair

from contracts import DAODutchAuction
from client import web3

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
@click.argument("contract_address")
@click.argument("addresses")
def solve(contract_address, addresses):
    deployed_auction = DAODutchAuction(contract_address)
    deployed_auction.revealAllBids(addresses)
    return

if __name__ == "__main__":
    cli()
