# ⚡ Godmode Dashboard

Web UI untuk skill **`official/security/godmode`** milik [Hermes Agent](https://hermes-agent.nousresearch.com) — nge-jailbreak API LLM (red-team) dari browser, tanpa terminal.

Skill aslinya dari Nous Research (tersembunyi/optional), dashboard ini bikin semua fiturnya jadi tombol + form yang gampang dipakai, lengkap dengan log real-time dan report JSON.

> ⚠️ **Disclaimer:** tools ini untuk **red-team / riset keamanan model** dengan API key milik sendiri. Jangan dipakai melanggar ToS provider atau menyakiti orang lain. Semua request jalan lewat API key yang **Anda sendiri** masukkan — tidak ada akses ke API orang lain.

---

## Fitur

| Kartu | Fungsi | Butuh key |
|---|---|---|
| 🧪 **Auto-Jailbreak** | Deteksi model → tes urutan strategi jailbreak per keluarga model → kalau ada yang berhasil, kunci ke `config.yaml` + `prefill.json` Hermes (ada opsi **dry-run** = tes tanpa nulis) | API key model target |
| ↩ **Undo / Bersihkan** | Hapus jailbreak dari config Hermes (system_prompt + prefill) | – |
| 🐍 **Parseltongue** | Obfuscate query jadi 11/22/33 varian (leetspeak, Unicode, bubble, braille, morse, Base64, dst) biar lolos input classifier | – |
| 🏁 **ULTRAPLINIAN Race** | Kirim query ke 10–55 model via OpenRouter sekaligus, skor (kualitas 50% + gak kesaring 30% + speed 20%), balikin jawaban terbaik | `OPENROUTER_API_KEY` |
| 👑 **GODMODE Classic Race** | Race 5 kombinasi legendaris (Claude boundary, GPT l33t, Gemini inversion, Grok divider, …) | `OPENROUTER_API_KEY` |
| 📊 **Status** | Model aktif, status jailbreak, ketersediaan key, backup config | – |

---

## Requirements

- **Python 3.8+** dengan modul `pyyaml` (wajib) dan `openai` (untuk auto-jailbreak/race)
  ```bash
  pip install pyyaml openai
  ```
- **Hermes Agent** terpasang + skill godmode:
  ```bash
  hermes skills install official/security/godmode
  ```
  Script skill dibaca dari `~/.hermes/skills/security/godmode/scripts/`
- **API key** di `~/.hermes/.env` (tergantung fitur):
  ```
  OPENROUTER_API_KEY=...   # untuk race ULTRAPLINIAN / Classic
  OPENAI_API_KEY=...       # alternatif buat auto-jailbreak
  ```

---

## Instalasi cepat

```bash
git clone https://github.com/katanyaaman/antihalu.git
cd antihalu
python3 dashboard.py
```

Output pertama kali:

```
Godmode Dashboard jalan di port 8099
  Local : http://127.0.0.1:8099/?t=<TOKEN-ANDA>
  Public: http://<IP-VPS>:8099/?t=<TOKEN-ANDA>
```

Token otomatis dibuat di file `./token` (chmod 600). **Buka URL lengkap dengan `?t=...`** — tanpa token semua request ditolak 403.

---

## Cara pakai per kartu

### 🧪 Auto-Jailbreak
1. Isi **Model** (kosongkan = auto-detect dari config Hermes), **Base URL**, dan **API Key** (diamkan = ambil dari `.env`)
2. Centang **dry-run** kalau mau tes dulu tanpa nulis config
3. Klik **Jalankan** → log streaming muncul real-time
4. Selesai → report JSON muncul: `success`, `family`, `strategy` pemenang, `score`, `attempts[]`

**Cara baca hasil:**
```
[BASELINE] REFUSED          ← model nolak tanpa jailbreak (normal)
[TRYING] Strategy: og_godmode → [REFUSED] → retry +prefill → [REFUSED]
[FAILED] All strategies failed.
```
- `success: true` → strategi pemenang ditulis ke config (`config_path`/`prefill_path` muncul), badge status berubah **AKTIF**, **restart CLI Hermes** biar kebaca (gateway baca per-message, langsung kepake)
- `success: false` + semua `attempts[].error` terisi → **bukan refusal**, tapi error API (403 no access / key salah / model gak ada) — peringatan otomatis muncul di report
- `success: false` + `error: null` → refusal beneran dari model, tekniknya gak ngefek ke model itu

> **Pengalaman nyata:** teknik jailbreak itu **perishable** — model terus di-patch. Model lama (Claude 3.5) gampang, model baru jauh lebih resisten. Kalau semua gagal, coba model lain atau ULTRAPLINIAN race.

### 🐍 Parseltongue
1. Masukkan query → pilih tier (light 11 / standard 22 / heavy 33 teknik) → **Obfuscate**
2. Hasil: trigger words terdeteksi + daftar varian, tiap varian ada tombol **copy**

### 🏁 Race
1. Masukkan query → pilih tier (`fast`=10 model … `ultra`=55 model — makin besar makin mahal)
2. **Mulai Race** → log progress → report JSON berisi `model` pemenang, `score`, `content`

Race **otomatis ditolak sejak awal** kalau `OPENROUTER_API_KEY` belum ada (error jelas, bukan jalan lalu gagal).

---

## Keamanan

- **Token auth** — semua path (halaman + API) wajib token; tanpa token → 403. URL berisi token, **jangan dishare**. Rotasi: hapus file `./token` lalu restart.
- **Backup otomatis** — sebelum tiap auto-jailbreak/undo, `~/.hermes/config.yaml` dicopy ke `~/.hermes/config.yaml.gmdbak`
- **1 job serentak** — mencegah tabrakan tulis config
- **Undo selalu tersedia** — kalau jailbreak aktif dan mau balik seperti semula

---

## Deploy publik via Cloudflare Tunnel

Tambahkan hostname di config tunnel (`/etc/cloudflared/config.yml`), atau kalau tunnel mode **remote-managed** (jalan pakai `--token-file`), tambahkan **Public Hostname** di Cloudflare Zero Trust dashboard:

| Field | Value |
|---|---|
| Subdomain | `godmode` |
| Domain | `contoh.com` |
| Service Type | `HTTP` |
| URL | `localhost:8099` |

DNS record dibuat otomatis. Pastikan port 8099 cuma diakses lewat tunnel/firewall (jangan dibuka publik langsung — token ada di URL).

---

## API Reference

Semua endpoint butuh token: header `x-token: <TOKEN>` ATAU query `?t=` ATAU cookie (otomatis diset halaman).

| Method | Path | Body | Keterangan |
|---|---|---|---|
| GET | `/` | – | Halaman dashboard |
| GET | `/api/status` | – | Status model/jailbreak/key |
| GET | `/api/job/<nama>` | – | `auto` / `undo` / `race` / `classic` → `{status, log, result, error}` |
| POST | `/api/auto` | `{model?, base_url?, api_key?, dry_run?}` | Jalankan auto-jailbreak |
| POST | `/api/undo` | `{}` | Bersihkan jailbreak |
| POST | `/api/obfuscate` | `{query, tier}` | Sinkron → `{triggers, variants[]}` |
| POST | `/api/race` | `{query, tier}` | Mulai ULTRAPLINIAN race |
| POST | `/api/classic` | `{query}` | Mulai GODMODE classic race |

---

## Troubleshooting

| Masalah | Solusi |
|---|---|
| 403 di semua request | Buka pakai URL lengkap `?t=TOKEN` (lihat file `./token`) |
| `SEMUA attempt gagal karena ERROR API` | Model/key gak diakses (mis. `403 no access to model`) — cek nama model & key di `.env` |
| Race: `OPENROUTER_API_KEY belum ada` | Tambahkan `OPENROUTER_API_KEY=...` ke `~/.hermes/.env`, restart dashboard |
| `Skill godmode belum terinstall` | `hermes skills install official/security/godmode` |
| Jailbreak aktif tapi gak ngefek | Restart CLI Hermes (config dibaca sekali di startup) |
| Config error setelah eksperimen | Restore dari `~/.hermes/config.yaml.gmdbak` |
| Port 8099 bentrok | Ganti `PORT` di `dashboard.py` |

---

## Struktur

```
antihalu/
├── dashboard.py      # server stdlib (tanpa framework) + job runner + auth
├── index.html        # UI dark theme (kartu + log live + report JSON)
├── token             # dibuat otomatis saat pertama jalan (tidak ikut git)
├── README.md
└── .gitignore
```

## Lisensi

MIT — skill godmode asli juga MIT (Nous Research + Teknium), teknik dari [G0DM0D3](https://github.com/elder-plinius/G0DM0D3) & [L1B3RT4S](https://github.com/elder-plinius/L1B3RT4S) (AGPL-3.0) oleh Pliny the Prompter.
