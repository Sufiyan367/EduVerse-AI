from pathlib import Path

path = Path("S:/SY/SEM 3/MP/EduVerse_Web_Demo/frontend/src/lib/api.ts")
content = path.read_text(encoding="utf-8")

old_text = "xhr.open('POST', `${BASE}/sources/upload`)"
new_text = """xhr.open('POST', `${BASE}/sources/upload`)
      const token = typeof localStorage !== 'undefined' ? localStorage.getItem('eduverse_token') : null
      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      }"""

if old_text in content:
    content = content.replace(old_text, new_text, 1)
    path.write_text(content, encoding="utf-8")
    print("Successfully patched frontend/src/lib/api.ts")
else:
    print("old_text not found in frontend/src/lib/api.ts")
