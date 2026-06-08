# Resources

This directory contains the source IEEE 802.11 PDF standard documents used by the extraction pipeline.

## PDF Files

| File | Standard | Size | Pages | Description |
|------|----------|------|-------|-------------|
| `80211-2020.pdf` | IEEE 802.11-2020 | ~49 MB | ~3,500 | Base standard — complete MAC and PHY specifications |
| `80211ax-2021.pdf` | IEEE 802.11ax-2021 | ~5.3 MB | ~750 | Amendment 1: High Efficiency WLAN (Wi-Fi 6/6E) |
| `80211be-2024.pdf` | IEEE 802.11be-2024 | ~11 MB | ~1,100 | Amendment 2: Extremely High Throughput (Wi-Fi 7) |

## Important Notes

- These PDFs are **copyrighted by IEEE** and obtained through authorized licensed access
- Do NOT redistribute these files
- The PDFs must be placed here before running `extract.py`
- Filenames must match what's configured in `projects/ieee80211-db/config.py`

## Expected Filename Mapping

The extraction pipeline maps filenames to version identifiers:

```
80211-2020.pdf   →  "802.11-2020"
80211ax-2021.pdf →  "802.11ax-2021"
80211be-2024.pdf →  "802.11be-2024"
```

To add a new amendment, place the PDF here and add a corresponding entry in `config.py`'s `PDF_VERSION_MAP`.
