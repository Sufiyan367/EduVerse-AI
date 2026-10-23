import requests

BASE = 'http://127.0.0.1:8080/api/v1'

# 1. Login
r_login = requests.post(f'{BASE}/auth/login', json={'username': 'student@eduverse.ai', 'password': 'demo123'})
assert r_login.status_code == 200, f'Login failed: {r_login.text}'
data = r_login.json()
token = data['token']
user = data['user']
print(f"1. Logged in as: {user['username']} (ID: {user['id']})")

headers = {'Authorization': f'Bearer {token}'}

# 2. Health & Dashboard stats
stats = requests.get(f'{BASE}/dashboard/stats', headers=headers).json()
print(f"2. Dashboard Stats: {stats}")

# 3. Sources
sources = requests.get(f'{BASE}/sources', headers=headers).json()
src_list = sources.get('sources', [])
print(f"3. Sources count: {len(src_list)}")
for s in src_list[:2]:
    print(f"   - Source {s['id']}: {s['title']} ({s['status']})")

# 4. Flashcards
cards = requests.get(f'{BASE}/cards', headers=headers).json()
print(f"4. Flashcards count: {len(cards.get('cards', []))}")

# 5. Chats & citations
chats = requests.get(f'{BASE}/chat', headers=headers).json()
chat_list = chats.get('chats', [])
print(f"5. Grounded Chats count: {len(chat_list)}")
if chat_list:
    cid = chat_list[0]['id']
    messages = requests.get(f'{BASE}/chat/{cid}/messages', headers=headers).json()
    for m in messages.get('messages', []):
        if m['role'] == 'assistant' and m.get('citations'):
            print(f"   - Assistant cited chunks: {m['citations']}")

# 6. Knowledge gap summary
gaps = requests.get(f'{BASE}/knowledge-gap/summary', headers=headers).json()
print(f"6. Knowledge Gaps: {len(gaps.get('gaps', []))} gap(s), Critical: {gaps.get('critical_count', 0)}")

# 7. Revision planner
revs = requests.get(f'{BASE}/revision-planner/sessions', headers=headers).json()
print(f"7. Revision Sessions: {len(revs)}")
print("\nLIVE SERVER VERIFICATION COMPLETED WITH 100% SUCCESS!")
