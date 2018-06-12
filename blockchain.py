# -*- coding: utf-8 -*-
"""
Created on Tue Jun 12 14:59:47 2018

@author: YangGao
"""
import hashlib
import json
from time import time
from uuid import uuid4
from flask import Flask, jsonify, request
from urllib.parse import urlparse

import config_bc as cf
first_proof = cf.FIRST_PROOF

class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        
        self.new_block(previous_hash = 1, proof = first_proof)
    
    def register_node(self, address):
        '''
        add a new node to the list of nodes
        
        Arguments:
            address: <str> address of the node.
        Return:
            None
        '''
        parsed_url = urlparse(address)
        if parsed_url.netloc:
            self.nodes.add(parsed_url.netloc)
        elif parsed_url.path:
            # Accepts an URL without scheme like '192.168.0.5:5000'.
            self.nodes.add(parsed_url.path)
        else:
            raise ValueError('Invalid URL')
        
        
    def new_block(self,proof,previous_hash=None):
        '''
        creates a new block and add it to chain
    
        Arguments:
            previous_hash: (optional) <str> hash of previous block
            proof: <str> the proof given by the proof of work
        
        Returns:
            return: <dict> new block
        '''
    
        block = {
            'index' : len(self.chain) + 1,
            'timestamp': time(),
            'transactions':self.current_transactions,
            'proof':proof,
            'previous_hash':previous_hash or self.hash(self.chain[-1])
            }
    
        self.current_transactions = []
    
        self.chain.append(block)
        return block

    
    def new_transaction(self, sender, recipient, amount):
        '''
        creates a new transaction and add it to the next block
    
        Arguments:
            sender: <str> address of the sender
            recipient: <str> address of the recipient
            amount: <str> amount
        Returns:
            return: <int> the index of block that holds this transaction
        '''
    
        self.current_transactions.append({
            'sender':sender,
            'recipient':recipient,
            'amount':amount,
            })
        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        '''
        creates a SHA-256 of a block
    
        Arguments:
            block: <dict> block
        Returns:
            return: <str> hash result
        '''
        block_string = json.dumps(block, sort_keys = True).encode()
        return hashlib.sha256(block_string).hexdigest()
    
    @property
    def last_block(self):
        '''returns the last block'''
        return self.chain[-1]
    
    def proof_of_work(self, last_proof):
        '''
        simple proof of work method:
            find a number p that hash(pp') contains 4 leading zeros
            p: previous proof
            p':new proof
            
        Argument:
            last_proof: <int>
        Return:
            return: <int>
        '''
        proof = 0
        while self.valid_proof(last_proof,proof) is False:
            proof += 1
        
        return proof
    
    @staticmethod
    def valid_proof(last_proof, proof):
        '''
        validates the proof: 
            does hash(last_proof,proof) contain 4 leading zeros?
        
        Arguments:
            last_proof: <int> previous proof
            proof: <int> current proof
        Return:
            result: <bool> True if corrent, False if not
        '''
        
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == '0000'
    
    
    
        
        
    def valid_chain(self, chain):
        '''
        Determine if a given blockchain is valid 
        looping through blocks and validating both the proof and hash
        
        Arguments:
            chain: <list> A blockchain
        Returns:
            <bool> True if valid, False if not
        '''
        last_block = chain[0]
        current_index = 1
        
        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print('\n-------------\n')
            
            if block['previous_hash'] != self.hash(last_block):
                return False
            
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False
            
            last_block = block
            current_index += 1
        
        return True
    
    def resolve_conflicts(self):
        '''
        consensus algorithm, resolves conflicts
        by replacing our chain with the longest one in the network
        
        return:
            <bool> True if chain was replaced, False if not
        '''
        neighbours = self.nodes
        new_chain = None
        
        max_length = len(self.chain)
        
        # grab and verify the chains from all the nodes in our network
        for node in neighbours:
            response = request.get(f'http://{node}/chain')
            
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']
                
                # check if the length is longer and the chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain
        
        # replace our chain if we found a new, valid chain that is longer than ours
        if new_chain:
            self.chain = new_chain
            return True
        
        return False
        
        
        
        
# instantiate our node
app = Flask(__name__)

# generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-', '')

# instantiate the blockchain
blockchain = Blockchain()

@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)
    
    blockchain.new_transaction(
            sender = '0',
            recipient = node_identifier,
            amount = 1,
            )
    
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)
    
    response = {
            'message': 'New Block Forged',
            'index': block['index'],
            'transactions': block['transactions'],
            'proof': block['proof'],
            'previous_hash': block['previous_hash'],
            }
    return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    
    required = ['sender','recipient','amount']
    if not all(k in values for k in required):
        return 'missing values', 400
    
    index = blockchain.new_transaction(values['sender'],values['recipient'], values['amount'])
    
    response = {'message':f'Transaction will be added to Block {index}'}
    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
            'chain':blockchain.chain,
            'length':len(blockchain.chain),
            }
    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    
    nodes = values.get('nodes')
    if nodes is None:
        return 'Error: please supply a valid list of nodes', 400
    
    for node in nodes:
        blockchain.register_node(node)
        
    response = {
            'message':'New nodes have been added',
            'total_nodes': list(blockchain.nodes),
            }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()
    
    if replaced:
        response = {
                'message': 'Our chain was replaced',
                'new_chain': blockchain.chain
                }
    else:
        response = {
                'message': 'Our chain is authorative',
                'chain': blockchain.chain
                }
    
    return jsonify(response), 200


if __name__ == '__main__':
    
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port)
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    