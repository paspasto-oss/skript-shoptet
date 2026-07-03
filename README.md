# Shoptet Importer – Midea/MDV PDF

Jednorazový testovací skript pre import produktov do Shoptetu z PDF cenníka Midea/MDV.

## Čo robí

- načíta PDF cenník Midea/MDV,
- vyberie iba kompletné zostavy: `split` a `monoblok`,
- ignoruje samostatné vnútorné/vonkajšie jednotky, rámčeky a príslušenstvo,
- nastaví:
  - výrobca: `Midea`,
  - dodávateľ: `Planning & Trading Slovakia s.r.o.`,
  - `code`: originálny kód `CMID...`,
  - `productNumber` a `partNumber`: model, napr. `MG2X-09-SP`,
- vytvorí CSV import pre Shoptet.

## Prečo CSV

Shoptet podporuje XLSX, CSV aj XML. CSV je najjednoduchšie na kontrolu a nemá skryté formátovanie Excelu.

Dôležité pravidlá Shoptetu:

- prvé stĺpce musia byť `code`, `pairCode`, `name`,
- pre nové produkty sú povinné `code`, `pairCode`, `name`, `price`,
- `code` musí byť jedinečný,
- `price` je iba číslo bez €,
- `defaultCategory` je potrebný, aby sa produkt zobrazil v e-shope,
- `includingVat = 0` znamená ceny bez DPH.

## Inštalácia

```bash
pip install -r requirements.txt
```

## Spustenie testu 10 produktov

```bash
python run_midea.py --pdf "VIP Cenník MIDEA + MDV 2026.pdf" --limit 10 --out out/test_10.csv --report out/kontrola_test_10.csv
```

## Spustenie celého importu

```bash
python run_midea.py --pdf "VIP Cenník MIDEA + MDV 2026.pdf" --out out/shoptet_midea_sety.csv --report out/kontrola_midea.csv
```

## Konfigurácia cien

V `config.json`:

```json
"price_mode": "recommended"
```

Použije odporúčanú cenníkovú cenu z PDF ako predajnú cenu.

Alebo:

```json
"price_mode": "margin",
"margin_multiplier": 2.15
```

Predajná cena = nákupná VIP cena × 2.15.

## Import do Shoptetu

Produkty → Import → vybrať CSV. Súbor je uložený ako UTF-8 s BOM a oddeľovač je bodkočiarka `;`.
