pragma solidity ^0.8.17;

// From https://billatnapier.medium.com/how-do-i-implement-symmetric-key-encryption-in-ethereum-14afffff6e42
contract Encryption {

    // WARNING: calling this will expose your secret, this is only for testing
    function encrypt(uint256 secret, uint256 key) public pure returns (uint256) {
        return secret ^ uint256(keccak256(abi.encodePacked(key)));
    }   

    function decrypt(uint256 code, uint256 key) public pure returns (uint256) {
        return code ^ uint256(keccak256(abi.encodePacked(key)));
    }   
}

