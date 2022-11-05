from bidder import generate_bidders
from crypto import G1, normalize, multiply
from crypto import symmetric_key_2D, generate_keypair

def test_key_recovery(dao_dutch_auction, auctioneers):
    print('Dutch auction', dao_dutch_auction)

    for a in auctioneers:
        npk = list(normalize(a.public_key))
        assert dao_dutch_auction.isBiddingOpen() == False
        dao_dutch_auction.setPublicKey(a.index, [int(npk[0]), int(npk[1])], {"from": a.address})

    assert dao_dutch_auction.isBiddingOpen() == True

    assert dao_dutch_auction.publishedKeys() == len(auctioneers)

    master_public_key = []
    master_public_key.append(dao_dutch_auction.masterPublicKey(0))
    master_public_key.append(dao_dutch_auction.masterPublicKey(1))

    #print("masterPublicKey", master_public_key)

    for a in auctioneers:
        npk = list(normalize(a.public_key))
        dao_dutch_auction.revealPrivateKey(a.index, a.private_key, {"from": a.address})
        assert dao_dutch_auction.isBiddingOpen() == False

    assert dao_dutch_auction.revealedKeys() == len(auctioneers)
    master_secret_key = dao_dutch_auction.masterSecretKey()
    #print("master secret key", master_secret_key)
    assert normalize(multiply(G1, master_secret_key)) == tuple(master_public_key)


def test_encryption(dao_dutch_auction, auctioneers):
    # Set public keys
    for a in auctioneers:
        npk = list(normalize(a.public_key))
        assert dao_dutch_auction.isBiddingOpen() == False
        dao_dutch_auction.setPublicKey(a.index, [int(npk[0]), int(npk[1])], {"from": a.address})

    master_public_key = []
    master_public_key.append(dao_dutch_auction.masterPublicKey(0))
    master_public_key.append(dao_dutch_auction.masterPublicKey(1))

    priv_k, pub_k = generate_keypair()

    #sym_key = symmetric_key_2D(tuple(master_public_key), priv_k)
    # TODO: why does pyecc functions not work for this
    sym_key = dao_dutch_auction.bn128_multiply.call([master_public_key[0], master_public_key[1], priv_k])[0]

    # Set private key
    for a in auctioneers:
        npk = list(normalize(a.public_key))
        dao_dutch_auction.revealPrivateKey(a.index, a.private_key, {"from": a.address})
        assert dao_dutch_auction.isBiddingOpen() == False

    master_secret_key = dao_dutch_auction.masterSecretKey()

    pub_k_2D = normalize(pub_k)
    exp_sym_key = dao_dutch_auction._sharedKey.call([int(pub_k_2D[0]), int(pub_k_2D[1])])

    assert exp_sym_key == sym_key


def test_bidding(dao_dutch_auction, auctioneers):
    # Set public keys
    for a in auctioneers:
        npk = list(normalize(a.public_key))
        assert dao_dutch_auction.isBiddingOpen() == False
        dao_dutch_auction.setPublicKey(a.index, [int(npk[0]), int(npk[1])], {"from": a.address})

    # Generate bidders
    bidders = generate_bidders(dao_dutch_auction.address, 10)
    bidder = bidders[0]
    bid_amount = 100000
    locked_wei = bid_amount * 2
    max_price = 1000000
    tx_hash = bidder.bid(bid_amount, max_price, locked_wei)
    active_bid = dao_dutch_auction.bids(bidder.account.address)

    # decrypt bids and verify
    sym_key = bidder.get_sym_key()
    bid_amount = dao_dutch_auction.decrypt(active_bid[1], sym_key)
    max_price = dao_dutch_auction.decrypt(active_bid[2], sym_key)
    assert bid_amount == bidder.bid_amount
    assert max_price == bidder.max_price


def test_mass_bidding():
    pass
