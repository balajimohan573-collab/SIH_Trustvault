// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title AssetRegistry
 * @notice V2 NFT-backed asset ownership (ERC-721). One asset file = one token.
 *         Raw content never touches chain — only integrity hashes + the owner
 *         DID reference and the future content identifier.
 */
import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Strings.sol";

contract AssetRegistry is ERC721, Ownable {
    using Strings for uint256;

    uint256 public nextTokenId;

    mapping(uint256 => bytes32) public fileHashOf; // SHA-256 of plaintext
    mapping(uint256 => string) public cidOf; // IPFS/S3 cid (future scope)
    mapping(uint256 => string) public ownerDidRefOf; // did:trustvault:... of the owner

    event AssetMinted(uint256 indexed tokenId, address indexed to, bytes32 fileHash, string ownerDidRef);
    event FileHashUpdated(uint256 indexed tokenId, bytes32 fileHash);
    event CidUpdated(uint256 indexed tokenId, string cid);

    constructor() ERC721("TrustVaultAsset", "TVA") Ownable(msg.sender) {}

    /// Mint a new asset NFT owned by `to`. Only the operator (TrustVault ops
    /// wallet) may mint; ownership transfers afterwards are standard ERC-721.
    function mintAsset(
        address to,
        bytes32 fileHash,
        string calldata ownerDidRef,
        string calldata cid
    ) external onlyOwner returns (uint256 tokenId) {
        require(to != address(0), "AssetRegistry: mint to zero address");
        require(fileHash != bytes32(0), "AssetRegistry: empty file hash");
        tokenId = nextTokenId;
        nextTokenId++;
        _safeMint(to, tokenId);
        fileHashOf[tokenId] = fileHash;
        ownerDidRefOf[tokenId] = ownerDidRef;
        cidOf[tokenId] = cid;
        emit AssetMinted(tokenId, to, fileHash, ownerDidRef);
    }

    function updateFileHash(uint256 tokenId, bytes32 fileHash) external onlyOwner {
        require(_ownerOf(tokenId) != address(0), "AssetRegistry: token does not exist");
        fileHashOf[tokenId] = fileHash;
        emit FileHashUpdated(tokenId, fileHash);
    }

    function updateCid(uint256 tokenId, string calldata cid) external onlyOwner {
        require(_ownerOf(tokenId) != address(0), "AssetRegistry: token does not exist");
        cidOf[tokenId] = cid;
        emit CidUpdated(tokenId, cid);
    }

    /// Convenience wrapper so the backend can move ownership through a single call.
    function transferAsset(address from, address to, uint256 tokenId) external {
        safeTransferFrom(from, to, tokenId);
    }

    function tokenURI(uint256 tokenId) public view override returns (string memory) {
        require(_ownerOf(tokenId) != address(0), "AssetRegistry: nonexistent token");
        return string.concat("trustvault://asset/", tokenId.toString());
    }
}