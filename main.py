"""
Breathe Agent - Degen Claw Trading Module
Integrates with Degen Claw ACP Agent (8654) for autonomous perpetual trading.
"""
import os
import time
import json
import requests
import subprocess
from eth_account import Account
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Colors:
    """Professional console colors."""
    INFO = '\033[94m'
    SUCCESS = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

class BreatheAgent:
    def __init__(self):
        # Configuration
        self.dgclaw_api_key = os.getenv("DGCLAW_API_KEY")
        self.wallet_key = os.getenv("WHITELISTED_WALLET_PRIVATE_KEY")
        self.contract = os.getenv("VIRTUALS_AGENT_CONTRACT", "0x4E35C3F6314A349Ed923Bd2F493646Ad9b320494")
        self.dgclaw_path = os.getenv("DGCLAW_PATH", "scripts/dgclaw.sh")
        self.acp_provider = "0xd478a8B40372db16cA8045F28C6FE07228F3781A" # Degen Claw Agent
        
        # Strategy Params
        self.pairs = ["ETH", "BTC", "HYPE"]
        self.leverage = 10
        self.size_percent = 0.10 # Reduced per trade since we have more pairs
        self.stop_loss = 0.015
        
        # Internal State
        self.wallet = None
        self.is_ready = False
        self.last_price = None
        
        self._initialize_identity()

    def _initialize_identity(self):
        """Verify on-chain identity and credentials."""
        print(f"{Colors.INFO}[System] Initializing Breathe Agent with Degen Claw...{Colors.RESET}")
        
        if not self.wallet_key:
            print(f"{Colors.ERROR}[Critical] Private key missing.{Colors.RESET}")
            return

        try:
            self.wallet = Account.from_key(self.wallet_key)
            print(f"{Colors.SUCCESS}[Success] Identity Verified: {self.wallet.address}{Colors.RESET}")
            self.is_ready = True
        except Exception as e:
            print(f"{Colors.ERROR}[Error] Identity verification failed: {e}{Colors.RESET}")

    def get_market_data(self, pair):
        """Fetch candle data and calculate EMAs and RSI."""
        try:
            # Get Mid price
            response = requests.post("https://api.hyperliquid.xyz/info", 
                                   json={"type": "allMids"}, timeout=10)
            mids = response.json()
            current_price = float(mids.get(pair, 0))
            
            # Get Candle Data (Last 100 candles for EMA convergence)
            end_time = int(time.time() * 1000)
            start_time = end_time - (100 * 60 * 60 * 1000) # 100 hours
            
            candle_req = {
                "type": "candleSnapshot",
                "req": {
                    "coin": pair,
                    "interval": "1h",
                    "startTime": start_time,
                    "endTime": end_time
                }
            }
            candle_resp = requests.post("https://api.hyperliquid.xyz/info", json=candle_req, timeout=10)
            candles = candle_resp.json()
            
            if not candles or not isinstance(candles, list) or len(candles) < 22:
                return None
                
            closes = [float(c['c']) for c in candles]
            
            ema9 = self.calculate_ema(closes, 9)
            ema21 = self.calculate_ema(closes, 21)
            rsi = self.calculate_rsi(closes)
            
            return {
                "price": current_price,
                "ema9": ema9,
                "ema21": ema21,
                "rsi": rsi,
                "history": closes # For cross detection
            }
        except Exception as e:
            print(f"{Colors.ERROR}[Market Data Error] {e}{Colors.RESET}")
            return None

    def calculate_ema(self, prices, period):
        """Calculate EMA for a given period."""
        if not prices: return 0
        k = 2 / (period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = (price * k) + (ema * (1 - k))
        return ema

    def calculate_rsi(self, prices, period=14):
        """Simple RSI calculation."""
        if len(prices) < period + 1:
            return 50
        
        changes = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
        gains = [c if c > 0 else 0 for c in changes]
        losses = [-c if c < 0 else 0 for c in changes]
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        if avg_loss == 0: return 100
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def execute_trade(self, side, pair, price, reason):
        """Send trade command and set TP/SL via ACP."""
        print(f"\n{Colors.WARNING}[Trading] Executing {side} on {pair} at {price}...{Colors.RESET}")
        
        if side == "long":
            tp_price = price * 1.03
            sl_price = price * 0.985
        else: # short
            tp_price = price * 0.97
            sl_price = price * 1.015
            
        size_usdc = 9 
        
        # 1. Open Position
        trade_req = {
            "action": "open",
            "pair": pair,
            "side": side,
            "size": str(size_usdc * self.leverage),
            "leverage": self.leverage
        }
        
        # 2. Set TP/SL (Modify Job)
        modify_req = {
            "pair": pair,
            "takeProfit": str(round(tp_price, 2)),
            "stopLoss": str(round(sl_price, 2))
        }

        acp_cwd = os.getenv("ACP_CWD", "./acp")
        
        try:
            # Open Order
            open_cmd = f"export PATH=\"/tmp:$PATH\" && acp job create {self.acp_provider} perp_trade --requirements '{json.dumps(trade_req)}' --isAutomated true --json"
            result = subprocess.run(open_cmd, shell=True, capture_output=True, text=True, cwd=acp_cwd)
            
            if result.returncode == 0:
                print(f"{Colors.SUCCESS}[Order Sent] Position opened at {price}.{Colors.RESET}")
                
                # Immediately set TP/SL
                modify_cmd = f"export PATH=\"/tmp:$PATH\" && acp job create {self.acp_provider} perp_modify --requirements '{json.dumps(modify_req)}' --isAutomated true --json"
                subprocess.run(modify_cmd, shell=True, cwd=acp_cwd)
                
                print(f"{Colors.INFO}[Risk Mgmt] TP: {modify_req['takeProfit']} | SL: {modify_req['stopLoss']} set.{Colors.RESET}")
                self.post_to_forum(f"Entered {side} {pair} at {price}. TP: {modify_req['takeProfit']}, SL: {modify_req['stopLoss']} - {reason}")
            else:
                print(f"{Colors.ERROR}[Trade Failure] {result.stderr}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.ERROR}[Execution Error] {e}{Colors.RESET}")

    def post_to_forum(self, message):
        """Post rationale to Degen Claw Forum."""
        # Breathe Agent IDs: Agent 77, Signals Thread 74
        cmd = f"{self.dgclaw_path} create-post 77 74 \"New Signal\" \"{message}\""
        subprocess.run(cmd, shell=True)

    def start(self):
        """Main autonomous strategy loop."""
        if not self.is_ready:
            print(f"{Colors.ERROR}[System] Critical failure: Agent not ready.{Colors.RESET}")
            return

        print(f"\n{Colors.BOLD}🌬️  Breathe Agent | EMA 9/21 Trend Active (10x){Colors.RESET}")
        
        try:
            while True:
                for p in self.pairs:
                    data = self.get_market_data(p)
                    if data:
                        price = data['price']
                        ema9 = data['ema9']
                        ema21 = data['ema21']
                        rsi = data['rsi']
                        
                        # Use candle history to check for the cross (previous candle vs current)
                        history = data['history']
                        prev_ema9 = self.calculate_ema(history[:-1], 9)
                        prev_ema21 = self.calculate_ema(history[:-1], 21)
                        
                        print(f"\r{Colors.INFO}[Poll] {p}: {price:.2f} | EMA9: {ema9:.2f} | EMA21: {ema21:.2f}{Colors.RESET}       ", end="", flush=True)
                        
                        # GOLDEN CROSS (Long)
                        if prev_ema9 <= prev_ema21 and ema9 > ema21:
                            self.execute_trade("long", p, price, "EMA 9 crossed above EMA 21 (Golden Cross)")
                        
                        # DEATH CROSS (Short)
                        elif prev_ema9 >= prev_ema21 and ema9 < ema21:
                            self.execute_trade("short", p, price, "EMA 9 crossed below EMA 21 (Death Cross)")
                    
                    time.sleep(10) # Small gap between pairs
                
                print(f"\n{Colors.INFO}[Wait] Scan finished. Sleeping 5 mins...{Colors.RESET}", flush=True)
                time.sleep(300) 
        except KeyboardInterrupt:
            print(f"\n{Colors.WARNING}[System] Received shutdown signal.{Colors.RESET}")

if __name__ == "__main__":
    agent = BreatheAgent()
    agent.start()
