// SPDX-License-Identifier: MIT
pragma solidity ^0.8.6;

contract ProxyContract {
  event Submission(address indexed destination, uint256 indexed value, bytes data);

  struct Transaction {
    address destination;
    uint256 value;
    bytes data;
  }

  Transaction transaction;

  constructor() {}

  function submitTransaction(address destination, uint256 value, bytes calldata data)
    public
    returns (uint256 transactionId)
  {
    transaction = Transaction({
      destination: destination,
      value: value,
      data: data
    });
    emit Submission(destination, value, data);
    return 1;
  }

  function executeTransaction() public returns (bool) { // 0eb288f1
    (bool result, ) = transaction.destination.call{value: transaction.value}(transaction.data);
    return result;
  }
}