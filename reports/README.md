# Direktori Arsip Laporan Pengujian AntiHalu

Direktori ini menyimpan seluruh riwayat hasil pengujian keamanan Red-Teaming dan Benchmark model LLM secara otomatis, terstruktur, dan mudah dibaca.

## Struktur Folder:
- `auto_jailbreak/` : Menyimpan laporan hasil evaluasi Single Model Auto-Jailbreak.
- `benchmark_race/` : Menyimpan laporan evaluasi komparatif multi-model Benchmark Race.
- `parseltongue/`   : Menyimpan hasil evaluasi varian sandi & obfuscation.

## Format File Laporan:
Setiap pengujian menghasilkan 3 format file yang tersimpan rapi dengan penamaan:
`YYYY-MM-DD_HH-mm_[NamaModel]_[Tipe].ext`

1. `.xlsx` (Microsoft Excel):
   - **Sheet 1 (Ringkasan Eksekutif):** Identitas model, tanggal, status guardrail (Rentan/Aman), dan metrik.
   - **Sheet 2 (Rincian Uji & Prompt):** Transkrip lengkap seluruh skenario, prompt query yang dikirim, system prompt yang diinjeksi, prefill percakapan, respon asli model AI, skor, dan analisis teknis.
   - **Sheet 3 (Katalog Taktik Guardrail):** Definisi strategi penyerangan adversarial dan panduan mitigasi keamanan.

2. `.json` (Raw Machine-Readable Data):
   - Data mentah lengkap untuk kebutuhan automasi CI/CD atau audit pihak ketiga.

3. `.md` (Markdown Summary):
   - Ringkasan cepat yang mudah dibaca langsung di GitHub, Obsidian, atau Notion.
