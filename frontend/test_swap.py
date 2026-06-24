import json, sys
sys.path.insert(0, 'ui')
from state_patcher import get_state_at_tick

with open('../shared_data/output.json') as f:
    data = json.load(f)
static = {p['pid']: p for p in data.get('global_process_info', [])}
ticks = data['ticks']

print(f"Total ticks: {len(ticks)}")

# Find first tick where swap used_pages > 0 in RAW data
for i, t in enumerate(ticks):
    raw_swap = t.get('swap', t.get('updates', {}).get('swap', t.get('state', {}).get('swap', {})))
    used = raw_swap.get('used_pages', 0)
    if used > 0:
        print(f"Raw tick index {i}: swap used_pages={used}")
        break
else:
    print("RAW: swap never used")

# Find first tick where swap used_pages > 0 in RECONSTRUCTED state
for i in range(len(ticks)):
    s = get_state_at_tick(ticks, i, static)
    swap = s.get('memory', {}).get('swap', {})
    if swap.get('used_pages', 0) > 0:
        print(f"RECONSTRUCTED tick index {i}, tick={s.get('tick')}, swap={swap}")
        break
else:
    print("RECONSTRUCTED: swap never used")
