// SPDX-License-Identifier: MIT
pragma solidity ^0.8.6;

contract Impersonator {
  // The first 3 MUST match the layout of the impersonated token:
  address public creator;
  uint256 public totalSupply;
  mapping (address => uint256) public balances;
  // Additional:
  address public target;

  constructor() {
    creator = msg.sender;
    totalSupply = 100000000000000000;
    balances[creator] = totalSupply;
  }

  function setTarget(address _target) public {
    target = _target;
  }

  function balanceOf(address _address) public view returns(uint256){
    return balances[_address];
  }

  function transfer(address receiver, uint256 amount) public returns(bool) {
    // This will execute the code in the target contract, in the context of
    // _this_ contract (using the totalSupply and balances in this storage)
    (bool success, bytes memory result) = target.delegatecall(
      abi.encodeWithSignature("transfer(address,uint256)", receiver, amount)
    );
    return success;
  }
}