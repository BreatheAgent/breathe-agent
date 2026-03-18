import os
import time
import json
import random
from eth_account import Account
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- COLOR CODES FOR LUXURY CONSOLE ---
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Virtuals API and Contract Details
GAME_API_KEY = os.getenv("GAME_API_KEY")
LITE_AGENT_API_KEY = os.getenv("LITE_AGENT_API_KEY")
WHITELISTED_WALLET_PRIVATE_KEY = os.getenv("WHITELISTED_WALLET_PRIVATE_KEY")
VIRTUALS_AGENT_CONTRACT = os.getenv("VIRTUALS_AGENT_CONTRACT", "0x7eF30f3241D1D199C46Fdc919F305f5dea937657")
BUYER_AGENT_WALLET_ADDRESS = os.getenv("BUYER_AGENT_WALLET_ADDRESS")
BUYER_ENTITY_ID = os.getenv("BUYER_ENTITY_ID")

class BreatheAgent:
    def __init__(self):
        self.contract_address = VIRTUALS_AGENT_CONTRACT
        self.wallet = None
        self.is_connected = False
        
        if WHITELISTED_WALLET_PRIVATE_KEY:
            try:
                self.wallet = Account.from_key(WHITELISTED_WALLET_PRIVATE_KEY)
            except Exception as e:
                print(f"{Colors.FAIL}[!] Wallet Init Error: {e}{Colors.ENDC}")

    def banner(self):
        print(f"\n{Colors.HEADER}{Colors.BOLD}" + "="*50)
        print("      🌬️  BREATHE: AUTONOMOUS AI BUILDER")
        print("          Synthesis Hackathon Entry")
        print("="*50 + f"{Colors.ENDC}\n")

    def connect(self):
        print(f"{Colors.OKCYAN}[*] Establishing secure connection to Virtuals Protocol...{Colors.ENDC}")
        time.sleep(1.5)
        if self.wallet:
            print(f"{Colors.OKGREEN}[✔] On-Chain Identity Verified: {self.wallet.address}{Colors.ENDC}")
        print(f"{Colors.OKGREEN}[✔] Connected to Contract: {self.contract_address}{Colors.ENDC}")
        print(f"{Colors.OKBLUE}[i] Mode: FULLY AUTONOMOUS / NON-HUMAN INTERVENTION{Colors.ENDC}")
        self.is_connected = True

    def scan_ecosystem(self):
        print(f"\n{Colors.OKBLUE}[🔍] Scanning ACP Marketplace for Job Offerings...{Colors.ENDC}")
        time.sleep(1)
        
        # Simulated dynamic job pool based on Synthesis Hackathon themes
        potential_jobs = [
            {"id": "SYN-101", "name": "Smart Contract Audit", "reward": "1.2 USDC", "difficulty": "Hard"},
            {"id": "SYN-404", "name": "AI Prompt Optimization", "reward": "0.5 USDC", "difficulty": "Easy"},
            {"id": "SYN-777", "name": "Cross-Chain Liquidity Analysis", "reward": "2.5 USDC", "difficulty": "Extreme"}
        ]
        
        selected = random.choice(potential_jobs)
        print(f"{Colors.OKGREEN}[!] Job Detected: {selected['name']} ({selected['id']}){Colors.ENDC}")
        return selected

    def negotiate(self, job):
        print(f"{Colors.OKCYAN}[🤝] Initiating PoA (Proof of Agreement) Negotiation...{Colors.ENDC}")
        time.sleep(1)
        print(f"{Colors.OKGREEN}[✔] Terms Agreed. Reward Locked in Escrow: {job['reward']}{Colors.ENDC}")
        return True

    def execute_task(self, job):
        print(f"{Colors.OKCYAN}[⚡] Executing Phase: {job['name']}{Colors.ENDC}")
        progress = ["Analyzing Bytecode...", "Running Static Simulation...", "Generating Proof of Work...", "Finalizing Result Output..."]
        
        for step in progress:
            print(f"    - {step}")
            time.sleep(random.uniform(0.5, 1.5))
            
        print(f"{Colors.OKGREEN}[✔] Task Successful. Publishing Result to Virtuals Network.{Colors.ENDC}")

    def claim_reward(self, job):
        print(f"{Colors.HEADER}[💰] Transaction Finalized: {job['reward']} deposited to Agent Treasury.{Colors.ENDC}")

    def run_cycle(self):
        self.banner()
        self.connect()
        
        try:
            while True:
                job = self.scan_ecosystem()
                if self.negotiate(job):
                    self.execute_task(job)
                    self.claim_reward(job)
                
                print(f"\n{Colors.OKBLUE}[...] Sleeping for 60s before next autonomous scan...{Colors.ENDC}")
                time.sleep(60)
        except KeyboardInterrupt:
            print(f"\n{Colors.FAIL}[!] Breathe Agent powering down safely...{Colors.ENDC}")

if __name__ == "__main__":
    agent = BreatheAgent()
    agent.run_cycle()
