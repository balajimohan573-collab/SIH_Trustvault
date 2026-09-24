import { expect } from "chai";
import { loadFixture } from "@nomicfoundation/hardhat-toolbox/network-helpers";
import { ethers } from "hardhat";

const OWNER_DID = "did:trustvault:holder";
const FILEHASH = ethers.keccak256(ethers.toUtf8Bytes("plaintext-bytes"));
const FILEHASH2 = ethers.keccak256(ethers.toUtf8Bytes("plaintext-bytes-2"));

async function deployAssetRegistry() {
  const [deployer, holder, stranger] = await ethers.getSigners();
  const Factory = await ethers.getContractFactory("AssetRegistry");
  const registry = await Factory.deploy();
  await registry.waitForDeployment();
  return { registry, deployer, holder, stranger };
}

describe("AssetRegistry (ERC-721)", () => {
  it("mints an NFT and records hash + DID reference", async () => {
    const { registry, holder } = await loadFixture(deployAssetRegistry);
    const tokenId = await registry.mintAsset.staticCall(
      holder.address,
      FILEHASH,
      OWNER_DID,
      ""
    );
    await registry.mintAsset(holder.address, FILEHASH, OWNER_DID, "");
    expect(await registry.ownerOf(tokenId)).to.equal(holder.address);
    expect(await registry.fileHashOf(tokenId)).to.equal(FILEHASH);
    expect(await registry.ownerDidRefOf(tokenId)).to.equal(OWNER_DID);
  });

  it("assigns sequential token ids", async () => {
    const { registry, holder } = await loadFixture(deployAssetRegistry);
    await registry.mintAsset(holder.address, FILEHASH, OWNER_DID, "");
    await registry.mintAsset(holder.address, FILEHASH2, OWNER_DID, "");
    expect(await registry.nextTokenId()).to.equal(2);
    expect(await registry.ownerOf(1)).to.equal(holder.address);
  });

  it("supports ERC-721 ownership transfers", async () => {
    const { registry, holder, stranger } = await loadFixture(deployAssetRegistry);
    await registry.mintAsset(holder.address, FILEHASH, OWNER_DID, "");
    await registry.connect(holder).transferAsset(holder.address, stranger.address, 0);
    expect(await registry.ownerOf(0)).to.equal(stranger.address);
  });

  it("restricts minting to the operator (owner)", async () => {
    const { registry, stranger } = await loadFixture(deployAssetRegistry);
    await expect(
      registry.connect(stranger).mintAsset(stranger.address, FILEHASH, OWNER_DID, "")
    ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");
  });

  it("rejects empty file hash and exposes a trustvault token URI", async () => {
    const { registry, holder } = await loadFixture(deployAssetRegistry);
    await expect(
      registry.mintAsset(holder.address, ethers.ZeroHash, OWNER_DID, "")
    ).to.be.revertedWith("AssetRegistry: empty file hash");
    await registry.mintAsset(holder.address, FILEHASH, OWNER_DID, "");
    expect(await registry.tokenURI(0)).to.equal("trustvault://asset/0");
  });
});