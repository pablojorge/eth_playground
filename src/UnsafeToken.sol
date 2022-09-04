// SPDX-License-Identifier: MIT
pragma solidity ^0.8.6;

contract UnsafeToken {
  address public creator;
  uint256 public totalSupply;
  mapping (address => uint256) public balances;

  event Transfer(address indexed _from, address indexed _to, uint256 _value);

  constructor() {
    creator = msg.sender;
    totalSupply = 10000;
    balances[creator] = totalSupply;
  }

  function balanceOf(address _address) public view returns(uint256){
    return balances[_address];
  }

  function transfer(address receiver, uint256 amount) public returns(bool) {
    address owner = msg.sender;
    require(amount > 0);
    // Instead of using require() or explicitly throwing, we just check and leave
    // returning false. If the return code is not checked, no obvious error will be 
    // detected by consumers.
    if (balances[owner] < amount) {
      return false;
    }
    balances[owner] -= amount;
    balances[receiver] += amount;
    emit Transfer(owner, receiver, amount);
    return true;
  }
}