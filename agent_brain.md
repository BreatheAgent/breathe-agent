# 🌬️ Breathe Agent | Strategy & Roadmap Brain

This file serves as the persistent memory and strategy guide for the Breathe Agent. Use this as a reference for current logic, active cüzdan (wallet) status, and future upgrade goals.

## 🧠 Current Core Logic (High-Frequency)
- **Timeframe**: 15 Minute (15m) candles.
- **Indicators**: 
  - **Fast EMA**: 5
  - **Slow EMA**: 13
  - **Signal**: Golden/Death Cross on 15m charts.
- **Risk Management**:
  - **Take Profit (TP)**: +1.0% (Symmetric)
  - **Stop Loss (SL)**: -1.0% (Symmetric)
  - **Leverage**: Dynamic (3x to 10x based on RSI confidence).
  - **Precision**: 6 decimal places for TP/SL (required for low-priced assets like JUP).

## 📊 Active Monitoring
- **Assets**: `SOL`, `TIA`, `ARB`, `JUP`, `ETH`, `BTC`, `HYPE`.
- **Primary Subaccount**: `0x39c4e869b344085a19e50ff1cf70d85baf64c72d` (Verified balance of ~$20.68).
- **Identity**: `0xB17fB2380734EC1C822B7F60D65165D98DEcC9`

## 🛠️ Infrastructure
- **ACP Integration**: Using `perp_trade` and `perp_modify` from Moltbot/Provider `0xd478...`.
- **Balance Detection**: Robust `curl` + `webData2` implementation to fetch Perp and L1 Spot balances.
- **Forum Logs**: Automatic signal posting to Degen Claw Forum (Agent 77, Thread 74).

## 🚀 Future Roadmap (Ideas & Upgrades)
- [ ] **Trailing Stop-Loss**: Lock in profits as they grow instead of a hard 1% TP.
- [ ] **Volume Confirmation**: Only entry trades if volume is above average to avoid fake-outs.
- [ ] **Expand Asset List**: Add more volatile 'Meme' perps if liquidity allows.
- [ ] **Sentiment Integration**: Connect to X (Twitter) sentiment to adjust position sizes.

---
*Created on 2026-03-26 - Optimized for Degen Claw Competition S1.*
