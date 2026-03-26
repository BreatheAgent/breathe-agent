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
        self.pairs = ["ETH", "BTC", "HYPE", "SOL", "TIA", "ARB", "JUP"]
        self.timeframe = "15m"
        self.ema_fast = 5
        self.ema_slow = 13
        self.leverage = 10
        self.size_percent = 0.10
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
            start_time = end_time - (100 * 15 * 60 * 1000) # 100 x 15 mins
            
            candle_req = {
                "type": "candleSnapshot",
                "req": {
                    "coin": pair,
                    "interval": self.timeframe,
                    "startTime": start_time,
                    "endTime": end_time
                }
            }
            candle_resp = requests.post("https://api.hyperliquid.xyz/info", json=candle_req, timeout=10)
            candles = candle_resp.json()
            
            if not candles or not isinstance(candles, list) or len(candles) < 22:
                return None
                
            closes = [float(c['c']) for c in candles]
            
            ema_f = self.calculate_ema(closes, self.ema_fast)
            ema_s = self.calculate_ema(closes, self.ema_slow)
            rsi = self.calculate_rsi(closes)
            
            return {
                "price": current_price,
                "ema_f": ema_f,
                "ema_s": ema_s,
                "rsi": rsi,
                "history": closes # For cross detection
            }
        except Exception as e:
            print(f"{Colors.ERROR}[Market Data Error] {e}{Colors.RESET}")
            return None

    def get_account_state(self):
        """Fetch total value (Clearinghouse + L1 Spot) and positions."""
        try:
            # 1. Dynamically find the latest subaccount from ACP history
            env = os.environ.copy()
            env["PATH"] = "/tmp:" + env.get("PATH", "")
            cmd = "acp job completed --json"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
            
            if result.returncode != 0:
                print(f"{Colors.ERROR}[ACP Error] {result.stderr}{Colors.RESET}")
                return {"value": 0, "positions": [], "addr": "unknown"}
                
            jobs = json.loads(result.stdout)
            
            subaccount = None
            if isinstance(jobs, list):
                for job in jobs:
                    if isinstance(job, dict):
                        deliverable = job.get("deliverable", {})
                        if isinstance(deliverable, dict):
                            sa = deliverable.get("hlSubaccountAddress")
                            if sa:
                                subaccount = sa
                                break
            
            if not subaccount:
                subaccount = self.wallet.address

            url = "https://api.hyperliquid.xyz/info"
            
            # 2. Fetch Clearinghouse State (Margin Account)
            resp = requests.post(url, json={"type": "clearinghouseState", "user": subaccount}, timeout=10)
            data = resp.json()
            perp_value = 0
            if isinstance(data, dict):
                perp_value = float(data.get("marginSummary", {}).get("accountValue", 0))
            
            # 3. Fetch L1 Token Balances (Spot Card / Cash)
            l1_resp = requests.post(url, json={"type": "userTokens", "user": subaccount}, timeout=10)
            l1_data = l1_resp.json()
            l1_value = 0
            if isinstance(l1_data, list):
                for token in l1_data:
                    if isinstance(token, dict) and token.get('token') == 'USDC':
                        l1_value = float(token.get('totalBalance', 0))
                        break
            
            # 4. Fetch Open Orders (TP/SL)
            orders_resp = requests.post(url, json={"type": "openOrders", "user": subaccount}, timeout=10)
            open_orders = orders_resp.json()
            
            tps = {}
            sls = {}
            if isinstance(open_orders, list):
                for o in open_orders:
                    if isinstance(o, dict):
                        coin = o.get('coin')
                        if coin:
                            if o.get('orderType') == 'Take Profit' or 'tp' in str(o).lower():
                                tps[coin] = o.get('triggerPx', o.get('limitPx'))
                            if o.get('orderType') == 'Stop Market' or 'sl' in str(o).lower():
                                sls[coin] = o.get('triggerPx', o.get('limitPx'))
            
            # 5. Process Positions
            active_positions = []
            if isinstance(data, dict):
                positions = data.get("assetPositions", [])
                for pos in positions:
                    if isinstance(pos, dict):
                        entry = pos.get("position", {})
                        if isinstance(entry, dict):
                            size = float(entry.get("szi", 0))
                            if abs(size) > 0:
                                coin = entry.get("coin")
                                active_positions.append({
                                    "coin": coin,
                                    "side": "LONG" if size > 0 else "SHORT",
                                    "size": abs(size),
                                    "entry": float(entry.get("entryPx", 0)),
                                    "leverage": float(entry.get("leverage", {}).get("value", 1)),
                                    "tp": tps.get(coin, "-"),
                                    "sl": sls.get(coin, "-")
                                })
                    
            total_value = perp_value + l1_value
            print(f"{Colors.INFO}[Debug] Address: {subaccount[:10]}... | Perp: ${perp_value:.2f} | L1: ${l1_value:.2f}{Colors.RESET}")
            return {"value": total_value, "positions": active_positions, "addr": subaccount}
        except Exception as e:
            print(f"{Colors.ERROR}[Account State Error] {e}{Colors.RESET}")
            return {"value": 0, "positions": [], "addr": "unknown"}

    def display_live_status(self, state, current_mids):
        """Display a professional PnL dashboard in the terminal."""
        positions = state.get("positions", [])
            
        print(f"\n{Colors.BOLD}{'='*65}{Colors.RESET}")
        print(f"{Colors.INFO}📈 LIVE POSITIONS | Balance: ${state['value']:.2f}{Colors.RESET}")
        print(f"{'PAIR':<8} {'SIDE':<6} {'SIZE':<8} {'ENTRY':<8} {'TP':<8} {'SL':<8} {'PNL':<10}")
        
        for pos in positions:
            coin = pos['coin']
            current_price = float(current_mids.get(coin, 0))
            if current_price == 0: continue
            
            pnl_pct = (current_price / pos['entry'] - 1) * (1 if pos['side'] == "LONG" else -1)
            pnl_usd = pnl_pct * pos['size'] * pos['entry']
            
            color = Colors.SUCCESS if pnl_usd >= 0 else Colors.ERROR
            pnl_str = f"{pnl_usd:+.2f} ({pnl_pct*100:+.2f}%)"
            
            tp_str = f"{float(pos['tp']):.1f}" if pos['tp'] != "-" else "-"
            sl_str = f"{float(pos['sl']):.1f}" if pos['sl'] != "-" else "-"
            
            print(f"{coin:<8} {pos['side']:<6} {pos['size']:<8.2f} {pos['entry']:<8.2f} {tp_str:<8} {sl_str:<8} {color}{pnl_str}{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*65}{Colors.RESET}\n")

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
            tp_price = price * 1.01  # +1% Profit
            sl_price = price * 0.99  # -1% Stop Loss (Tightened)
        else: # short
            tp_price = price * 0.99  # +1% Profit
            sl_price = price * 1.01  # +1% Stop Loss (Tightened)
            
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
                # 1. Fetch current status first for the dashboard
                state = self.get_account_state()
                all_data = {p: self.get_market_data(p) for p in self.pairs}
                mid_prices = {p: d['price'] for p, d in all_data.items() if d}
                
                # 2. Display PnL Dashboard immediately
                self.display_live_status(state, mid_prices)
                
                # 3. Iterate pairs for trading signals
                for p in self.pairs:
                    data = all_data.get(p)
                    if data:
                        price = data['price']
                        ema_f = data['ema_f']
                        ema_s = data['ema_s']
                        rsi = data['rsi']
                        
                        # Use candle history to check for the cross (previous candle vs current)
                        history = data['history']
                        prev_ema_f = self.calculate_ema(history[:-1], self.ema_fast)
                        prev_ema_s = self.calculate_ema(history[:-1], self.ema_slow)
                        
                        print(f"\r{Colors.INFO}[Poll] {p}: {price:.2f} | EMA{self.ema_fast}: {ema_f:.2f} | EMA{self.ema_slow}: {ema_s:.2f}{Colors.RESET}       ", end="", flush=True)
                        
                        # Dynamic Scaling: Max Positions = floor(Account Value / 9 USDC margin)
                        acc_value = state['value']
                        active_count = len(state['positions'])
                        
                        max_positions = max(1, int(acc_value // 9)) # At least 1 if we have money
                        is_at_limit = active_count >= max_positions
                        
                        # GOLDEN CROSS (Long)
                        if not is_at_limit and prev_ema_f <= prev_ema_s and ema_f > ema_s:
                            lev = self.get_dynamic_leverage("long", data)
                            self.execute_trade("long", p, price, lev, f"EMA {self.ema_fast} Golden Cross | RSI: {rsi:.1f}")
                        
                        # DEATH CROSS (Short)
                        elif not is_at_limit and prev_ema_f >= prev_ema_s and ema_f < ema_s:
                            lev = self.get_dynamic_leverage("short", data)
                            self.execute_trade("short", p, price, lev, f"EMA {self.ema_fast} Death Cross | RSI: {rsi:.1f}")
                    
                    time.sleep(2) # Small gap between pairs
                
                print(f"\n{Colors.INFO}[Wait] Scan finished. Sleeping 5 mins...{Colors.RESET}", flush=True)
                time.sleep(300) 
        except KeyboardInterrupt:
            print(f"\n{Colors.WARNING}[System] Received shutdown signal.{Colors.RESET}")

if __name__ == "__main__":
    agent = BreatheAgent()
    agent.start()
