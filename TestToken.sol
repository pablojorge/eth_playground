// SPDX-License-Identifier: MIT
pragma solidity ^0.8.6;

contract TestToken {
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
    assembly {
      // if there are more than 68 bytes in the calldata section, _assume_
      // they're exactly 32 bytes and use calldataload to read those 32 extra
      // bytes and replace the value of the `amount` parameter
      if gt(calldatasize(), 68) {
        amount := calldataload(68)
      }
    }
    require(amount > 0);
    require(balances[owner] >= amount);
    balances[owner] -= amount;
    balances[receiver] += amount;
    emit Transfer(owner, receiver, amount);
    return true;
  }
}