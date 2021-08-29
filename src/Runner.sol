// SPDX-License-Identifier: MIT
pragma solidity ^0.8.6;

contract Runner {
  event Submission(address indexed destination, uint256 indexed value, bytes data);
  event Execution(address indexed destination, bool result);

  struct Transaction {
    address destination;
    uint256 value;
    bytes data;
  }

  Transaction[] transactions;

  constructor() {}

  function submitTransaction(address destination, uint256 value, bytes calldata data)
    public
    returns (uint256 transactionId)
  {
    transactions.push(Transaction({
      destination: destination,
      value: value,
      data: data
    }));
    emit Submission(destination, value, data);
    return 1;
  }

  // $ solc --hashes src/Runner.sol
  // ======= src/Runner.sol:Runner =======
  // Function signatures:
  // 069549bc: executeTransactions()
  // c6427474: submitTransaction(address,uint256,bytes)

  // Returns true is _all_ executions are successful:
  function executeTransactions() public returns (bool) { // 069549bc 
    bool ret = true;
    for (uint i=0; i < transactions.length; i++) {
      Transaction memory transaction = transactions[i];
      (bool result, ) = transaction.destination.call{value: transaction.value}(transaction.data);
      ret = ret && result;
      emit Execution(transaction.destination, result);
    }
    return ret;
  }
}