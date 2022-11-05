// SPDX-License-Identifier: UNLICENSED

pragma solidity 0.8.17;

import "./Encryption.sol";
import "./BN128.sol";

contract DAODutchAuction is BN128, Encryption {
    // Mapping of auctioneer to their individual public key
    mapping(address => uint256[2]) public auctioneerPublicKeys;
    // Mapping of auctioneer to their individual private key
    mapping(address => uint256) public auctioneerPrivateKeys;

    // PublicKey for the Auction
    uint256[2] public masterPublicKey;
    // PrivateKey for the Auction
    uint256 public masterSecretKey;

    // ETH Addresses of designated auctioneers
    address[] public auctioneers;

    // Counters for number of published sub pub/priv keys
    uint256 public publishedKeys = 0;
    uint256 public revealedKeys = 0;

    // Timestamp after which bidding is over
    uint256 public bidClosingTime;

    // Keep track of number of bidders, needed for an all bid reveal step
    uint256 public bidCount = 0;

    // Map of msg.sender to locked ETH
    mapping(address => uint256) public lockedEth;

    // Map of msg.sender to their current Bid
    mapping(address => Bid) public bids;

    // Mapping of result submitter addr to array of addresses in order of winning bids
    mapping(address => address[]) public allBids;

    struct Bid {
        uint256 encryptedBid;
        uint256 encryptedAmount;
        uint256[2] bidderPublicKey;
    }

    constructor(address[] memory _auctioneers, uint256 _bidClosingTime) {
        address prevAddr = address(0);
        for (uint256 i = 0; i < _auctioneers.length; i++) {
            // Prevents duplicates
            require(uint160(_auctioneers[i]) > uint160(prevAddr), "Auctioneers must be ordered");
            prevAddr = _auctioneers[i];
            auctioneers.push(_auctioneers[i]);
        }
        bidClosingTime = _bidClosingTime;
    }

    function isBiddingOpen() public view returns (bool) {
        return publishedKeys == auctioneers.length && revealedKeys == 0;
    }

    function hasBiddingClosed() public view returns (bool) {
        return block.timestamp >= bidClosingTime;
    }

    function setPublicKey(uint256 index, uint256[2] memory publicKey) public {
        // Verify sender is auctioneer
        require(auctioneers[index] == msg.sender, "Unauthorized");

        // Verify sender has not published key yet
        require(auctioneerPublicKeys[msg.sender][0] == 0, "Key already set");

        // Verify pub key is valid
        require(bn128_is_on_curve(publicKey), "Invalid public key");

        auctioneerPublicKeys[msg.sender] = publicKey;

        // Increment published key count
        publishedKeys += 1;

        // Add public key to master public key
        //  (techincally, this can happen off-chain, but do it here for simplicity)
        masterPublicKey = bn128_add([masterPublicKey[0], masterPublicKey[1], publicKey[0], publicKey[1]]);
    }

    function revealPrivateKey(uint256 index, uint256 privKey) public {
        // Verify sender is auctioneer
        require(auctioneers[index] == msg.sender, "Unauthorized");

        // require that privKey not already set
        require(auctioneerPrivateKeys[msg.sender] == 0, "Key already set");

        // require that mul(G1, privKey) == pubKey 
        uint256[2] memory derivedPubKey = bn128_multiply([G1x, G1y, privKey]);
        require(derivedPubKey[0] == auctioneerPublicKeys[msg.sender][0], "Invalid private key");
        require(derivedPubKey[1] == auctioneerPublicKeys[msg.sender][1], "Invalid private key");


        masterSecretKey += privKey;
        revealedKeys += 1;

        if (revealedKeys == auctioneers.length) {
          masterSecretKey = masterSecretKey % GROUP_ORDER;

          // verify final secret key, otherwise auction fails
          uint256[2] memory derivedMasterPubKey = bn128_multiply([G1x, G1y, masterSecretKey]);

          // TODO: Instaed of require here, this could trigger a force-abort of the auction...
          require(derivedMasterPubKey[0] == masterPublicKey[0], "Invalid master private key");
          require(derivedMasterPubKey[1] == masterPublicKey[1], "Invalid master private key");
        }
    }

    // Can be called more than 1 time technically
    function bid(uint256 encryptedAmount, uint256 encryptedMax, uint256[2] memory publicKey) public payable {
        require(isBiddingOpen(), "Bidding is not open");
        require(!hasBiddingClosed(), "Bidding has closed");

        // Lock ETH towards bid
        lockEth();

        // Check that the public key of the bidder is valid
        require(bn128_is_on_curve(publicKey), "Invalid public key");

        // Save bid and increment counter
        bids[msg.sender] = Bid(encryptedAmount, encryptedMax, publicKey);
        bidCount += 1;
    }

    // Can be called more than 1 time
    function lockEth() public payable {
        lockedEth[msg.sender] += msg.value;
    }

    // Function that reveals all bids, sorted by valid(ordered by maxPrice descending, then address), then invalid bids ordered by address
    //function revealAllBids(address[] memory bidders) {
    //    if bidders.length == 0, reset buffer
    //    // require bids to be in decreasing order by maxPrice then address
    //    Bid memory currentBid;
    //    uint256 postedBids = postAllBids[msg.sender].length;

    //    if (postedBids) {
    //        currentBid = postedBids[];
    //    }
    //    for (uint256 i = 0; i < bidders.length; i++) {
    //    }
    //    currentBid = 
    //    if revealedBids[msg.sender].length == 
    //}

    // TODO: use challenge/response period instead
}
