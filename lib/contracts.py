import json
import os
from web3 import Web3

script_dir = os.path.dirname(__file__)
relative_build_dir = "../brownie/build/contracts"

# TODO: move these instances to a central location
web3 = Web3()

CONTRACT_NAMES = ["DAODutchAuction"]

for name in CONTRACT_NAMES:
    artifact_path = os.path.join(script_dir, relative_build_dir, f"{name}.json")
    with open(artifact_path) as f:
        build_json = json.load(f)
        globals()[name] = web3.eth.contract(abi=build_json["abi"], bytecode=build_json["bytecode"])
