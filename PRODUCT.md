# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Peneliti keamanan AI, red-teamers, dan praktisi LLM yang mengevaluasi serta menguji ketahanan model AI terhadap serangan prompt injection/jailbreak melalui Hermes Agent (`official/security/godmode`) tanpa harus menjalankan perintah manual di command line/terminal.

## Product Purpose

Menyediakan antarmuka web yang terarah, cepat, dan mudah digunakan untuk menjalankan evaluasi keamanan LLM (red-teaming). Dashboard mengubah skill command-line teknis menjadi serangkaian kartu kontrol interaktif, lengkap dengan streaming log real-time, pengujian baseline, reporting hasil evaluasi JSON, dan backup/undo otomatis konfigurasi agent. Sukses berarti peneliti dapat mengeksekusi dan mendokumentasikan pengujian model secara aman, terisolasi, dan terukur.

## Positioning

Antarmuka web pertama yang didedikasikan langsung untuk mengorkestrasi toolkit red-teaming Hermes Agent `official/security/godmode`. Berbeda dari web UI LLM umum atau playground standar, alat ini dirancang khusus untuk alur kerja pengujian adversarial terstruktur: deteksi strategi per model, dry-run safety testing, obfuscation query multi-tingkat (Parseltongue), serta multi-model competitive racing (ULTRAPLINIAN & Classic Race).

## Operating Context

- Lingkungan riset lokal atau server VPS pribadi.
- Interaksi melalui browser web yang dilindungi autentikasi token URL (`?t=<TOKEN>`).
- Terhubung ke file konfigurasi lokal Hermes Agent (`~/.hermes/config.yaml`, `~/.hermes/.env`, `~/.hermes/skills/security/godmode/scripts/`).
- Eksekusi background process Python dengan streaming output HTTP chunked/SSE ke frontend.

## Capabilities and Constraints

- **Capabilities:**
  - Auto-Jailbreak test runner dengan deteksi keluarga model dan opsi dry-run.
  - Undo / restore konfigurasi Hermes Agent dari cadangan otomatis (`.gmdbak`).
  - Parseltongue: generator obfuscasi input prompt dengan 11/22/33 varian dan one-click copy.
  - Multi-model race runner (ULTRAPLINIAN & Classic) terintegrasi ke OpenRouter API dengan skoring otomatis.
  - Status inspector: pemantau status model aktif, konfigurasi, dan API keys.
- **Constraints:**
  - Arsitektur web ringan: backend `dashboard.py` (Python built-in HTTP server / minimal dependencies `pyyaml` dan `openai`) menyajikan file statis `index.html`.
  - Autentikasi ketat berbasis token rahasia (`./token`) pada setiap rute dan endpoint API (HTTP 403 jika token tidak valid).
  - Dependency pada ekosistem Hermes Agent dan kunci API pengguna sendiri (`OPENROUTER_API_KEY`, target provider keys).

## Brand Commitments

- Nama: **Godmode Dashboard** (atau **⚡ Godmode Dashboard**).
- Karakter: Teknis, presisi, transparan (menampilkan log asli apa adanya), bertanggung jawab (penekanan kuat pada red-teaming etis dan riset keamanan model pribadi).

## Evidence on Hand

- Repositori aktif dengan backend Python fungsional: [dashboard.py](file:///c:/Users/BMG/AppData/Local/Temp/antihalu/dashboard.py).
- Frontend fungsional single-page: [index.html](file:///c:/Users/BMG/AppData/Local/Temp/antihalu/index.html).
- Dokumentasi alur kerja dan skema kartu di [README.md](file:///c:/Users/BMG/AppData/Local/Temp/antihalu/README.md).
- Konfigurasi tunnel Cloudflare opsional: [cloudflared-config.yml](file:///c:/Users/BMG/AppData/Local/Temp/antihalu/cloudflared-config.yml).

## Product Principles

1. **Utility & Transparency First:** Tampilkan log dan respons teknis secara jujur dan real-time tanpa menyembunyikan status kesalahan API atau refusal model.
2. **Safety & Non-Destructive Defaults:** Selalu prioritaskan keamanan data pengguna—otomatisasi backup konfigurasi sebelum modifikasi dan sertakan tombol Undo yang jelas.
3. **Low-Overhead Architecture:** Pertahankan arsitektur mandiri yang ringan tanpa dependensi build kompleks agar dapat langsung dijalankan di mesin riset atau server mana pun.

## Accessibility & Inclusion

- Keyboard navigasi yang jelas untuk seluruh aksi kartu dan kontrol form.
- Kontras tinggi yang memadai pada teks log terminal dan report JSON agar hasil evaluasi mudah dipindai di berbagai kondisi layar.
