from client import web3
import os
script_dir = os.path.dirname(__file__)
relative_path = "../scripts/mnemonic.txt"
full_path = os.path.join(script_dir, relative_path)

mnemonic = ""

MAX_ACCOUNTS = 100

with open(full_path) as f:
    mnemonic = f.readlines()[0].rstrip()

def get_account(index: int):
    if index >= MAX_ACCOUNTS:
        raise Exception("Index exceeds account limit")
    return web3.eth.account.from_mnemonic(mnemonic, account_path=f"m/44'/60'/0'/0/{index}")
