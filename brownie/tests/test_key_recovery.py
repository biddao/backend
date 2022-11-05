from crypto import G1, normalize, multiply

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
