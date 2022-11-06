# DAO Dutch Auction

#### A sealed-bid dutch auction for <i>fair & strategic</i> aggregate purchasing

Bidders can submit their bid with a maximum clearing price above which their bid invalidates

All bid information is encrypted with a shared key

Upon reveal of the decryption key, the auction settles at the maximum valid clearing price


## Improvement on existing auctions

* <b>Optimized UX</b>
  * bidder has no reveal requirement
  * lister has instant access to funds upon settlement
* <b>Distributed key generation:</b> prevents auctioneer manipulation
* <b>Max price threshold:</b> bidders can opt out if value exceeds a threshold they set
* <b>Bid obfuscation:</b> values encrypted, concealed by additional contract-locked value</b>

Inspired by the [ConstitutionDAO 2021 Sotheby's bid attempt](https://www.coindesk.com/tech/2021/11/19/constitutiondao-outbid-for-first-printing-of-americas-founding-document-in-sothebys-auction/)

### Auction Phases

#### 1. Deployment

Constructor parameters

* `auctioneers`: array of ETH addresses for the auctioneers
* `expiration`: time after which the auction is closed


#### 2. Key generation

Each auctoneer must generate an ECDSA keypair for the auction and commit their public key

`setPublicKey(uint256 index, uint256[2] publicKey)`

`index` can be found with an `eth_call` request to `getIndex(address auctioneer)`


#### 3. Bidding

A bidder generates an ECDSA public/private key pair and uses ECDH to compute a symmetric key for encrypting bid values. This key can be discarded if needed

`bid(uint256 encryptedBidAmount, uint256 encryptedMaxPrice, uint256[2] bidderPublicKey){value: ethToLock}`

For a bid to be valid, the `bidAmount` must be less than or equal to `maxPrice` and `ethToLock` must exceed `bidAmount`

Encryption and decryption follow a [keccack256 based algorithm](https://billatnapier.medium.com/how-do-i-implement-symmetric-key-encryption-in-ethereum-14afffff6e42) 


#### 4. Reveal

Each auctioneer reveals their private key

`revealPrivateKey(uint256 privateKey)`

The resulting masterPrivateKey must generate the masterPublicKey or the all bidders are refunded


#### 5. Settlement

Two mechanisms for settling

a.) A challenge & response period during which anyone can propose a result for the auction 

`settle(clearingPrice, totalBids)`

Where `clearingPrice` is the settled price of the listed item, and `totalBids` is the amount of ETH in valid bid towards the item. 

In some cases totalBids can exceed clearingPrice, in which case bidders will each receive `clearingPrice/totalBids` ownership and a refund of `(totalBids - clearingPrice)/clearingPrice` % of their bidAmount

b.) On-chain reveal

All bids can be decrypted on-chain in a deterministic order that generates the result

If needed, this can be chained into multiple calls

`revealAllBids(address[] bidders)`



### Testing

* setup environment `nix-shell` or install brownie
* `cd brownie && brownie test`


### References

* [EthDKG](https://github.com/PhilippSchindler/EthDKG)
