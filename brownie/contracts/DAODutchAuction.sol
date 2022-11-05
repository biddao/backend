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

    // Result tracking for on-chain decryption of results (not always needed)
    mapping(address => address[]) public postedBids;
    mapping(address => Result) public results;
    address public resultSubmitter;

    struct Bid {
        address sender;
        uint256 encryptedBidAmount;
        uint256 encryptedMaxPrice;
        uint256[2] bidderPublicKey;
    }

    struct Result {
        uint256 maxPrice;
        uint256 filledAtPrice;
        uint256 totalBidAtPrice;
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

    // TODO: make this internal
    function _sharedKey(uint256[2] memory publicKey) public returns (uint256) {
        require(revealedKeys == auctioneers.length, "Master private key not set");
        uint256[2] memory result = bn128_multiply([publicKey[0], publicKey[1], masterSecretKey]);
        return result[0];
    }

    function _decryptBid(Bid memory _bid) internal returns (uint256 bidAmount, uint256 maxPrice) {
        uint256 symKey = _sharedKey(_bid.bidderPublicKey);
        bidAmount = decrypt(_bid.encryptedBidAmount, symKey);
        maxPrice = decrypt(_bid.encryptedMaxPrice, symKey);
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
    function bid(uint256 encryptedBidAmount, uint256 encryptedMaxPrice, uint256[2] memory _publicKey) public payable {
        require(isBiddingOpen(), "Bidding is not open");
        require(!hasBiddingClosed(), "Bidding has closed");

        // Lock ETH towards bid
        lockEth();

        // Check that the public key of the bidder is valid
        require(bn128_is_on_curve(_publicKey), "Invalid public key");

        // Save bid and increment counter
        bids[msg.sender] = Bid(msg.sender, encryptedBidAmount, encryptedMaxPrice, _publicKey);
        bidCount += 1;
    }

    // Can be called more than 1 time
    function lockEth() public payable {
        lockedEth[msg.sender] += msg.value;
    }

    // Function that reveals all bids, sorted by valid(ordered by maxPrice descending, then address), then invalid bids ordered by address
    // Since only 1 bid can be saved per address, ordering by maxPrice or validity then address will guarantee no duplicates
    // TODO: instead perhaps let bidders include a hash their decrypted values, so 2xSLOAD + decryption doesn't need to happen...
    function revealAllBids(address[] memory bidders) public {
        // Ensure no one has completed result
        require(resultSubmitter == address(0), "Result already generated");

        // If bidders is empty, reset the buffers
        if (bidders.length == 0) {
            delete postedBids[msg.sender];
            results[msg.sender] = Result(0,0,0);
            return;
        }

        // Check results
        // Bids need to be in decreasing order by maxPrice then for invalid bids only address
        Bid memory currentBid;
        Bid memory nextBid;

        // If bids already posted, use latest as current
        if (postedBids[msg.sender].length > 0) {
            currentBid = bids[postedBids[msg.sender][postedBids[msg.sender].length - 1]];
        }

        // For each bidder presented
        for (uint256 i = 0; i < bidders.length; i++) {

            // Get the next bid
            nextBid = bids[bidders[i]];

            // This prob not needed
            require(nextBid.sender != bidders[i], "Invalid bid");

            // Assert public key has been set
            require(nextBid.bidderPublicKey[0] != 0, "Invalid bid");

            bool currentBidValid = true;
            bool nextBidValid = true;

            (uint256 nextBidAmount, uint256 nextBidMaxPrice) = _decryptBid(nextBid);

            // Bid Amount cannot exceed max price
            if (nextBidAmount > nextBidMaxPrice) {
                nextBidValid = false;
            }
            // Bid Amount cannot exceed lockedEth
            if (nextBidValid && nextBidAmount > lockedEth[nextBid.sender]) {
                nextBidValid = false;
            }

            // If currentBid is set, compare with nextBid, verify follows protocol
            if (currentBid.bidderPublicKey[0] != 0) {
                (uint256 currentBidAmount, uint256 currentBidMaxPrice) = _decryptBid(currentBid);

                // Check if bids are valid

                // Bid Amount cannot exceed max price
                if (currentBidAmount > currentBidMaxPrice) {
                    currentBidValid = false;
                }

                // Bid Amount cannot exceed lockedEth
                if (currentBidValid && currentBidAmount > lockedEth[currentBid.sender]) {
                    currentBidValid = false;
                }

                // Valid bids must come first and be adjacent
                if (nextBidValid) require(currentBidValid, "Valid bid incorrectly ordered");

                // Raise exception if submitted in wrong order
                if (nextBidValid) {
                    // While next bid still valid max price must be in descending order
                    require(currentBidMaxPrice >= nextBidMaxPrice, "Results must be in order of decreasing max price");

                    // If compared bids have same maxPrice, addresses must be in descending orderj
                    require(currentBid.sender > nextBid.sender , "Bid sender incorrectly ordered");
                } else {
                    // If nextBid is invalid
                    // If currentBid is also invalid, senders must be in descending order
                    if (currentBidValid == false) {
                      require(currentBid.sender > nextBid.sender, "Bid sender incorrectly ordered");
                    }
                }

            }
            // Else if current bid is not set, we assume nextBid, valid or invalid
            //  was ordered appropriately and check it on next iteraiton

            // Add nextBid.sender to postedBids
            postedBids[msg.sender].push(nextBid.sender);
            currentBid = nextBid;

            Result memory currentResult = results[msg.sender];

            // Add next bid to results while next bid valid and nextMaxPrice is unchanged or totalbids is less than max price
            if (
                nextBidValid && 
                (nextBidMaxPrice == currentResult.maxPrice 
                  || (currentResult.totalBidAtPrice + currentResult.filledAtPrice < currentResult.maxPrice)
                )
            ) {

                // If next bid has lower maxPrice, increment filledAtPrice, reset totalBidAtprice
                if (currentResult.maxPrice != nextBidMaxPrice) {
                    currentResult.maxPrice = nextBidMaxPrice;
                    // Add last bidAtPrice amount to total filled
                    currentResult.filledAtPrice += currentResult.totalBidAtPrice;
                    // Reset totalBidAtPrice to nextBidAmount
                    currentResult.totalBidAtPrice = nextBidAmount;
                } else {
                    // If nextBid has same maxPrice, just increment totalBidAtPrice
                    currentResult.totalBidAtPrice += nextBidAmount;
                }

                // Update result
                results[msg.sender] = currentResult;
            }

            // Result becomes final once all bids accounted for
            if (postedBids[msg.sender].length == bidCount) {
                // Auction is finalized

                // TODO: Add reserve scenario

                // handle case where maxPrice isn't exceeded
                if (currentResult.totalBidAtPrice + currentResult.filledAtPrice < currentResult.maxPrice) {
                    // maxPrice becomes the total amount bid
                    currentResult.maxPrice = currentResult.totalBidAtPrice + currentResult.filledAtPrice;

                    // No division of bidders at max price necessary, set equal to filledAtPrice
                    currentResult.totalBidAtPrice = currentResult.filledAtPrice;
                } else {
                    currentResult.filledAtPrice = currentResult.maxPrice - currentResult.filledAtPrice;
                }

                resultSubmitter = msg.sender;

                // TODO here: (1) Create a DAO with maxPrice shares (2) Send maxPrice funds there
            }
        }

    }

    // Optional, withdraw to an address
    function withdraw() public {
        // TODO: If auctoin expired and masterPrivateKey doesn't match masterPublicKey, abort aucton. Let user withdraw all funds
        require(resultSubmitter != address(0), "Auction not final");

        Result memory result = results[resultSubmitter];

        uint256 ethRefund = lockedEth[msg.sender];

        Bid memory userBid = bids[msg.sender];
        require(userBid.bidderPublicKey[0] != 0, "Bid does not exist");

        (uint256 bidAmount, uint256 maxPrice) = _decryptBid(userBid);

        // Clear this out first
        lockedEth[msg.sender] = 0;

        // If bid invalid (amount greater than bidder maxPrice, maxPrice less than result max, or bidAmount greater than locked ETH)
        // Return all ETH
        if (bidAmount > maxPrice || maxPrice < result.maxPrice || bidAmount > lockedEth[msg.sender]) {
            (bool success, ) = msg.sender.call{value: ethRefund}("");
            require(success, "Failed to send Ether");
        } else if (maxPrice == result.maxPrice ) {
            ethRefund = ethRefund * result.filledAtPrice / result.totalBidAtPrice;
            (bool success, ) = msg.sender.call{value: ethRefund}("");
            require(success, "Failed to send Ether");
            // Handle case where maxPrice is exactly equal to result max. Gets a fractional result
        } else if (maxPrice < result.maxPrice) {
            // ethRefund = 0;
            // Send back to user all ETH tokens, with amount ethRefund
            // ERC20.transfer()
        }

    }
  
    // TODO: use challenge/response period instead
}
