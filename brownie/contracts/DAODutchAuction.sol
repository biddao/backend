contract DAODutchAuction {
    mapping(address => uint256[2]) public publicKeys;

    uint256[2] public masterPublicKey;
    uint256 public masterSecretKey;

    address[] public auctioneers;
    uint256 public publishedKeys = 0;
    uint256 public revealedKeys = 0;
    uint256 public bidClosingTime;

    mapping(address => uint256) public lockedEth;
    mapping(address => Bid) public bids;

    mapping(address => address[]) public allBids;

    struct Bid {
        uint256 encryptedBid;
        uint256 encryptedAmount;
        uint256[2] bidderPublicKey;
    }

    constructor(address[] memory _auctioneers, uint256 _bidClosingTime) {
        for (var i = 0; i < auctioneers.length; i++) {
            isAuctioneer[auctioneers[i]] = true;
        }
        bidClosingTime = _bidClosingTime;
    }

    function setPublicKey(uint256 index, uint256[2] memory publicKey) public {
        require(auctioneers[index] == msg.sender);
        require(auctioneers[msg.sender] == true, "Unauthorized");

        // TODO: is one check here sufficient?
        require(publicKeys[msg.sender][0] == 0, "Key already set");

        // require(check_bn128_is_on_curve(public_key))

        publicKeys[msg.sender] = publicKey;
        publishedKeys += 1;

        // masterPublicKey = bn128_add([masterPublicKey[0], masterPublicKey[1], publicKey[0], publicKey[1]);
    }

    function revealPrivateKey(uint256 index, uint256 privKey) public {
        require()
        // require that privKey not already set
        // require that mul(G1, privKey) == pubKey 
        // masterSecretKey += privKey
        revealedKeys += 1;
        //if (revealedKeys == auctioneers.length)
        //   masterSecretKey = mulmod(masterSecretKey, GROUP_ORDER)
    }

    function isAuctionLive() public view returns (bool) {
        return publishedKeys == auctioneers.length && revealedKeys.length == 0;
    }

    // Can be called more than 1 time
    function bid(uint256 encryptedAmount, uint256 encryptedMax, uint256[2] calldata publicKey) payable {
        require(isAuctionLive(), "Bidding is not open");
        require(block.timestamp < bidClosingTime, "Bidding has closed");

        lockEth();
        // require(check_bn128_is_on_curve(publicKey));
        bids[msg.sender] = Bid(encryptedAmount, encryptedMax, publicKey);
    }

    // Can be called more than 1 time
    function lockEth() payable {
        lockedEth[msg.sender] += msg.value;
    }

    function postAllBids(address[] memory bidders) {
        // require bids to be in decreasing order by maxPrice then address
        Bid memory currentBid;
        uint256 postedBids = postAllBids[msg.sender].length;

        if (postedBids) {
            currentBid = postedBids[];
        }
        for (uint256 i = 0; i < bidders.length; i++) {
        }
        currentBid = 
    }
}
