# 🎮 Guess The Word

**Guess The Word** is an interactive Discord bot built in **Python** that gamifies vocabulary learning and language practice.  
Players receive hints and must guess the correct word — earning streaks, tracking stats, and unlocking harder challenges as they go.

---

## 🚀 Features

- **🌍 Multi-language Guessing:**  
  Accepts guesses in over **10+ languages** (including English, Polish, Spanish, French, German, and more).  
  Hints currently appear only in **English** and **Polish**, but the recognition engine supports multilingual input.

- **📊 Smart Stat Tracking:**  
  Every player’s performance is stored in lightweight JSON data files — tracking:
  - Words completed  
  - Longest streak  
  - Average accuracy  
  - Most-missed categories  
  This allows personalized progression and difficulty scaling over time.

- **🧠 Intelligent Hint System:**  
  Dynamic hint generation adapts to your progress — showing partial word patterns or semantic clues while avoiding spoilers.

- **⚙️ Modular Architecture:**  
  Built using `discord.py` with a clean, extensible structure:
  - `/memorize_random_pl` — randomized Polish learning mode  
  - `/practice` — choose your own word or category  
  - Separate modules for word loading, hint generation, and statistics  
  This makes it easy to add new languages, word lists, or command sets.

---

## 🛠️ Tech Stack

- **Language:** Python 3.10+
- **Libraries:** `discord.py`, `asyncio`, `json`, `random`
- **Structure:** Multi-file modular project (commands, utils, config)
- **Data:** Custom JSON-based persistent stat tracking

---

## 🕹️ Example Gameplay

```text
🧩 Theme: "forest fire"
Hint: p_______ _______

You: forest fire
✅ Correct! The Polish word was **pożar lasu** 🌲🔥
Your streak: 5 | Longest streak: 7
