#!/bin/bash
# Breathe Agent Funding Script
echo "--- Funding Breathe Agent Trading Account (10 USDC) ---"
export PATH="/tmp:$PATH"
acp job create 0xd478a8B40372db16cA8045F28C6FE07228F3781A perp_deposit --requirements '{"amount":"10"}' --isAutomated true
echo "--- Funding Job Created Successfully ---"
