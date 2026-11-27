# 02 — Cari Bakiye (GL Entry ve Payment Ledger Entry)

Kaynak: ERPNext `develop`. Kod kopyalanmadı; yalnızca kavram ve 5 satırlık alıntı.

## 1. İşaret kuralı (net)

Defterde **negatif tutar yoktur**. İşaret, satırın *hangi kolonda* durduğuyla ifade edilir: `debit` ve `credit` ayrı, pozitif sütunlardır. Net bakiye her zaman `debit − credit` ile hesaplanır.

- Debit = borç artışı, credit = alacak artışı.
- Hesaplanan bakiye her zaman "debit bakiyesi" cinsindendir; alacak bakiyesi eksi sayı olur.

## 2. Alanlar ve anlamları

**GL Entry** (muhasebe defteri, her hesap için satır): `posting_date`, `account`, `debit`, `credit`, `debit_in_account_currency` / `credit_in_account_currency` (döviz), `party_type` + `party`, `voucher_type` + `voucher_no` (kaynak belge), `against_voucher_type` + `against_voucher` (hangi faturaya mahsup), `is_cancelled`, `is_opening`, `docstatus`.

**Payment Ledger Entry** (cari/ödeme defteri, yalnızca Receivable/Payable hesap hareketleri): tek `amount` alanı (işaretli), `account_type` (Receivable/Payable), `against_voucher_no`, `delinked`.

Bakiye için fark: GL Entry *hesap merkezli*dır ve borç/alacak iki sütun; PLE *taraf merkezli*dir, tek işaretli tutar tutar ve fatura başına kalan/anapara mutabakatını (mahsup, iade) takip eder.

## 3. Bakiye formülü ve örnek

`bakiye = Σ debit − Σ credit` (filtre: `party_type`, `party`, `is_cancelled = 0`, `docstatus = 1`).

Örnek (müşteri):

| Tarih | Belge | Debit | Credit |
|---|---|---|---|
| 01.03 | Satış faturası | 1.000 | |
| 15.03 | Tahsilat | | 400 |
| 20.03 | İade (credit note) | | 100 |

Bakiye = 1.000 − 400 − 100 = **500 TL**. Debit negatif olsaydı (müşteri fazla ödeme) sonuç eksi olur ve "avans" sayılır.

## 4. İptal / iade

- **Iade** ayrı bir belgedir; normal kayıt gibi ters yönlü satır üretir (credit).
- **Iptal** iki aşamalıdır: (1) orijinal satırlar `is_cancelled = 1` yapılır; (2) ters satır (debit↔credit takas) oluşturulur ve o da `is_cancelled = 1` **olarak** işaretlenir. Böylece iptal edilen belge bakiye sorgularında tamamen görünmez.
- GL Entry tek başına iptal edilemez; kaynak belge iptal edilir.

## 5. Basit Django modelimize öneriler

`Partner` + `LedgerEntry(date, description, debit, credit)`:

1. `debit`/`credit` alanlarını `DecimalField(max_digits=14, decimal_places=2)` tut; negatif yazımı yasakla (`PositiveDecimalField` veya `CheckConstraint`). Net bakiye = `debit - credit`.
2. `is_cancelled` yerine `status` (`posted` / `cancelled`) ve `reverses` (self-FK) alanı ekle; iptal = ters kayıt + orijinali `cancelled` yapmak. Silme yok.
3. `entry_type` (invoice / payment / credit_note) ve `document_no` sakla; iade = `credit_note`.
4. Bakiye asla kolona yazılmasın; `aggregate(Sum(...))` ile hesaplanan property + `(partner, date)` index kullan (kesinlikle cache'lenirse invalidation şart).
5. Aynı kayıtta hem debit hem credit > 0 yasaklayan `CheckConstraint` ekle; `date` yerine `posting_date` adını tercih et.

## 6. Tuzaklar

- `is_cancelled = 0` filtresini unutmak (çift sayım/iade hatası).
- GL Entry'yi `docstatus` yerine `is_opening` ile karıştırmak; açılış bakiyesi ayrı satır.
- Float kullanmak; para hesabında yuvarlama hatası verir.
- Debit/credit'i tek işaretli sütuna toplarken işaret yönünü ters koymak (müşteri borcu eksi görünür).
- Her belge için Σdebit = Σcredit denkliğini doğrulamamak.
- `voucher_no` = belge no ile `against_voucher` = mahsup edilen fatura no'yu aynı sanmak.

## 7. Kaynak

- `erpnext/accounts/doctype/gl_entry/gl_entry.json` (alanlar: satır 9–57, 59–378; `is_cancelled` 272–277)
- `erpnext/accounts/doctype/gl_entry/gl_entry.py` (bakiye kuralı 334–351; iptal engeli 328–331)
- `erpnext/accounts/doctype/payment_ledger_entry/payment_ledger_entry.json` (10–30, 99–124)
- `erpnext/accounts/party.py` (bakiye toplamı 1042–1049; taraf hesabı 488–553)
- `erpnext/accounts/general_ledger.py` (ters kayıt 647–767; `set_as_cancel` 770–781)
- `erpnext/accounts/utils.py` (PLE işaret kuralı 2177–2187)
