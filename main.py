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

    def get_account_state(self):
        """Fetch total account value and active position count."""
        try:
            url = "https://api.hyperliquid.xyz/info"
            user_address = self.wallet.address
            payload = {"type": "clearinghouseState", "user": user_address}
            
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            # 1. Total Account Value (USD)
            summary = data.get("marginSummary", {})
            account_value = float(summary.get("accountValue", 0))
            
            # 2. Active Positions & PnL
            active_positions = []
            positions = data.get("assetPositions", [])
            for pos in positions:
                entry = pos.get("position", {})
                size = float(entry.get("s", 0))
                if abs(size) > 0:
                    coin = entry.get("coin")
                    entry_price = float(entry.get("entryPx", 0))
                    leverage = float(entry.get("leverage", {}).get("value", 1))
                    side = "LONG" if size > 0 else "SHORT"
                    active_positions.append({
                        "coin": coin,
                        "side": side,
                        "size": abs(size),
                        "entry": entry_price,
                        "leverage": leverage
                    })
                    
            return {"value": account_value, "positions": active_positions}
        except:
            return {"value": 0, "positions": []}

    def display_live_status(self, state, current_mids):
        """Display a professional PnL dashboard in the terminal."""
        positions = state.get("positions", [])
        if not positions:
            return
            
        print(f"\n{Colors.BOLD}{'='*50}{Colors.RESET}")
        print(f"{Colors.INFO}📈 LIVE POSITIONS | Balance: ${state['value']:.2f}{Colors.RESET}")
        print(f"{'PAIR':<10} {'SIDE':<6} {'SIZE':<10} {'ENTRY':<10} {'PNL':<10}")
        
        for pos in positions:
            coin = pos['coin']
            current_price = float(current_mids.get(coin, 0))
            if current_price == 0: continue
            
            # PnL Calculation
            pnl_pct = (current_price / pos['entry'] - 1) * (1 if pos['side'] == "LONG" else -1)
            pnl_usd = pnl_pct * pos['size'] * pos['entry']
            
            color = Colors.SUCCESS if pnl_usd >= 0 else Colors.ERROR
            pnl_str = f"{pnl_usd:+.2f} ({pnl_pct*100:+.2f}%)"
            
            print(f"{coin:<10} {pos['side']:<6} {pos['size']:<10.2f} {pos['entry']:<10.2f} {color}{pnl_str}{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*50}{Colors.RESET}\n")

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

    def get_dynamic_leverage(self, side, data):
        """Determine leverage (3x, 5x, 10x) based on RSI and trend strength."""
        rsi = data.get('rsi', 50)
        
        # High Confidence (10x): Trend is fresh and RSI supports it
        if side == "long" and rsi < 45: return 10
        if side == "short" and rsi > 55: return 10
        
        # Moderate Confidence (7x): Standard cross
        if 40 < rsi < 60: return 7
        
        # High Risk / Volatile (3x): RSI is near extremes or trend is extended
        return 3

    def execute_trade(self, side, pair, price, leverage, reason):
        """Send trade command with dynamic leverage and set TP/SL."""
        print(f"\n{Colors.WARNING}[Trading] Executing {side} on {pair} at {price} ({leverage}x)...{Colors.RESET}")
        
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
            "size": str(size_usdc * leverage),
            "leverage": leverage
        }
        
        # 2. Set TP/SL (Modify Job)
        modify_req = {
            "pair": pair,
            "takeProfit": str(int(tp_price)),
            "stopLoss": str(int(sl_price))
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
                self.post_to_forum(f"Entered {side} {pair} at {price} ({leverage}x). TP: {modify_req['takeProfit']}, SL: {modify_req['stopLoss']} - {reason}")
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
                        
                        # Dynamic Scaling: Max Positions = floor(Account Value / 9 USDC margin)
                        state = self.get_account_state()
                        acc_value = state['value']
                        active_count = len(state['positions'])
                        
                        # Display PnL Dashboard
                        mid_prices = {pair: self.get_market_data(pair)['price'] for pair in self.pairs if self.get_market_data(pair)}
                        self.display_live_status(state, mid_prices)
                        
                        max_positions = max(1, int(acc_value // 9)) # At least 1 if we have money
                        is_at_limit = active_count >= max_positions
                        
                        # GOLDEN CROSS (Long)
                        if not is_at_limit and prev_ema9 <= prev_ema21 and ema9 > ema21:
                            lev = self.get_dynamic_leverage("long", data)
                            self.execute_trade("long", p, price, lev, f"EMA 9 Golden Cross | RSI: {rsi:.1f} | Cap: {active_count}/{max_positions}")
                        
                        # DEATH CROSS (Short)
                        elif not is_at_limit and prev_ema9 >= prev_ema21 and ema9 < ema21:
                            lev = self.get_dynamic_leverage("short", data)
                            self.execute_trade("short", p, price, lev, f"EMA 9 Death Cross | RSI: {rsi:.1f} | Cap: {active_count}/{max_positions}")
                    
                    time.sleep(10) # Small gap between pairs
                
                print(f"\n{Colors.INFO}[Wait] Scan finished. Sleeping 5 mins...{Colors.RESET}", flush=True)
                time.sleep(300) 
        except KeyboardInterrupt:
            print(f"\n{Colors.WARNING}[System] Received shutdown signal.{Colors.RESET}")

if __name__ == "__main__":
    agent = BreatheAgent()
    agent.start()
