from random import randrange

from brownie import web3, TestERC20
from bidder import generate_bidders, decrypt_bids, get_all_bids, rank_bid_result
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
    print(get_all_bids(dao_dutch_auction.address))

    # Set private key
    for a in auctioneers:
        npk = list(normalize(a.public_key))
        dao_dutch_auction.revealPrivateKey(a.index, a.private_key, {"from": a.address})
        assert dao_dutch_auction.isBiddingOpen() == False

    print(decrypt_bids(dao_dutch_auction.address))
    print("ordered bids")
    print(rank_bid_result(dao_dutch_auction.address, decrypt_bids(dao_dutch_auction.address)))


def test_bidding_same_max_price(dao_dutch_auction, auctioneers):
    # Set public keys
    for a in auctioneers:
        npk = list(normalize(a.public_key))
        assert dao_dutch_auction.isBiddingOpen() == False
        dao_dutch_auction.setPublicKey(a.index, [int(npk[0]), int(npk[1])], {"from": a.address})

    # Generate bidders & bid all same max_price
    bidders = generate_bidders(dao_dutch_auction.address, 10)

    bid_amount = 100000
    locked_wei = bid_amount * 2
    max_price = 1000000

    for bidder in bidders:
        tx_hash = bidder.bid(bid_amount, max_price, locked_wei)

    # Set private key
    for a in auctioneers:
        npk = list(normalize(a.public_key))
        dao_dutch_auction.revealPrivateKey(a.index, a.private_key, {"from": a.address})
        assert dao_dutch_auction.isBiddingOpen() == False

    print(decrypt_bids(dao_dutch_auction.address))
    print("ordered bids")
    result = rank_bid_result(dao_dutch_auction.address, decrypt_bids(dao_dutch_auction.address))
    print("realized price", result.realized_price)
    print("total bids at price", result.total_bid)

    # Test revealing bids
    bidders = [bid.bidder for bid in result.ordered_bids]
    dao_dutch_auction.revealAllBids(bidders, {"from": auctioneers[0].address})

    (max_price, total_bid) = dao_dutch_auction.results(auctioneers[0].address)
    print("realized price", max_price)
    print("total bids", total_bid)


def test_randomized_bids(dao_dutch_auction, auctioneers):
    # Set public keys
    for a in auctioneers:
        npk = list(normalize(a.public_key))
        assert dao_dutch_auction.isBiddingOpen() == False
        dao_dutch_auction.setPublicKey(a.index, [int(npk[0]), int(npk[1])], {"from": a.address})

    NUM_BIDS = 20
    bidders = generate_bidders(dao_dutch_auction.address, NUM_BIDS)

    starting_balances = [
        web3.eth.get_balance(bidder.account.address)
        for bidder in bidders
    ]

    MAX_PRICE = web3.eth.get_balance(bidders[0].account.address) * 2

    for bidder in bidders:
        max_price = randrange(0, MAX_PRICE)
        bid_amount = randrange(0, max_price)
        cur_balance = web3.eth.get_balance(bidders[0].account.address)
        locked_wei = min(int(bid_amount), int(cur_balance / 3))
        tx_hash = bidder.bid(bid_amount, max_price, locked_wei, skip_assertions=True)

    # Set private key
    for a in auctioneers:
        npk = list(normalize(a.public_key))
        dao_dutch_auction.revealPrivateKey(a.index, a.private_key, {"from": a.address})
        assert dao_dutch_auction.isBiddingOpen() == False

    result = rank_bid_result(dao_dutch_auction.address, decrypt_bids(dao_dutch_auction.address))
    bidder_addrs = [bid.bidder for bid in result.ordered_bids]

    # Reveal bids
    dao_dutch_auction.revealAllBids(bidder_addrs, {"from": auctioneers[0].address})

    # Check on chain results == local results
    (realized_price, total_bid) = dao_dutch_auction.results(auctioneers[0].address)
    assert realized_price == result.realized_price
    assert total_bid == result.total_bid


    votes_token = TestERC20.at(dao_dutch_auction.votesToken())

    print("total vote balance", votes_token.balanceOf(dao_dutch_auction.address))

    # Test withdraw
    for bidder in bidders:
        current_balance = web3.eth.get_balance(bidder.account.address)
        transaction = dao_dutch_auction.withdraw({"from": bidder.account.address})
        print("vote balance", votes_token.balanceOf(bidder.account.address))

    print("total vote balance", votes_token.balanceOf(dao_dutch_auction.address))
