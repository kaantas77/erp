# 05 — Raporlama ve Liste Ekranı Desenleri

Kaynak: ERPNext `develop` (GPLv3). Sadece okundu; kod kopyalanmadı, kod bloğu yok. Kavram ve alan (kolon/filtre) isimleri anlatılır.

Üç rapor aynı iskeleti paylaşır: *filtre tanımı (JS) → `execute(filters)` → dönen 4'lü (kolonlar, satırlar, mesaj, grafik, toplam satırı bilgisi)*. Kolonlar rapor çalışırken **dinamik** üretilir; filtre bir kolonu açar/kapatır.

## 1. Stok bilanço raporu (Stock Balance)

**Filtreler** (`erpnext/public/js/stock_balance_report.js` → ortak fonksiyon): company (varsayılan), from_date (varsayılan −1 ay, zorunlu), to_date (bugün, zorunlu), item_group, item_code (çoklu seçim), warehouse (çoklu), warehouse_type, valuation_field_type (Currency/Float), include_uom, show_alt_uom_balance, show_variant_attributes, show_stock_ageing_data, ignore_closing_balance, include_zero_stock_items (varsayılan açık), show_dimension_wise_stock. Envanter boyutları (`project` vb.) ayrıca enjekte edilir.

**Kolonlar**: item_code (sabitlenmiş), item_name, item_group, warehouse (sabit), [boyut kolonları], stock_uom, **bal_qty, bal_val** (sabit), opening_qty, opening_val, in_qty, in_val, out_qty, out_val, val_rate, reserved_stock, company. Koşullu ekler: yaşlandırma (average_age, earliest_age, latest_age), varyant özniteliği, alternatif birim (alt_uom + alt_uom_bal_qty, bal_qty'den hemen sonra).

Rapor tipi **Script Report**, `add_total_row = 1`; ayrıca DuckDB "snapshot" sürümü var (hızlı yol).

## 2. Cari alacak raporu (Accounts Receivable)

**Filtreler** (`accounts_receivable.js`): company (zorunlu), report_date (tek tarih! aralık değil), finance_book, cost_center, project, party_type, party, party_account, ageing_based_on (Posting Date/Due Date), age_as_on (Report Date/Today), range (varsayılan "30, 60, 90, 120"), customer_group, payment_terms_template, sales_partner, sales_person, territory. Onay kutuları: group_by_party, based_on_payment_terms, show_future_payments, show_delivery_notes, show_sales_person, show_remarks, in_party_currency, for_revaluation_journals, ignore_accounts (voucher bazında grupla).

**Kolonlar**: posting_date, party_type, party, party_account, customer_name, customer_primary_contact, cost_center, project, voucher_type, voucher_no, due_date, invoiced, paid, credit_note, **outstanding**, age (gün), dinamik yaş kolonları (range0 = "<0", sonra "0-30", "30-60", "60-90", "90-120", "120-Above"), currency; koşullu: future_ref/future_amount/remaining_balance, po_no, delivery_notes, territory, customer_group, sales_person, remarks.

## 3. Stok defteri (Stock Ledger)

**Filtreler**: company (zorunlu), from_date/to_date (zorunlu), warehouse, item_code, item_group, batch_no, brand, voucher_no, project, include_uom, valuation_field_type, segregate_serial_batch_bundle.

**Kolonlar**: date (datetime), item_code, item_name, stock_uom, [boyutlar], in_qty, out_qty, qty_after_transaction, warehouse, item_group, brand, description, incoming_rate, valuation_rate ("Avg Rate"), in_out_rate, stock_value, stock_value_difference, voucher_type, voucher_no, serial_and_batch_bundle / batch_no / serial_no (gizli, bayrakla açılır), project, company. `add_total_row = 0` — hareket defteri, toplamı anlamsız.

## 4. Gruplama ve toplam desenleri

- **Rapor düzeyi toplam**: rapor tanımındaki `add_total_row` bayrağı; satırlar bir liste, toplamlar çerçeve tarafından sayısal kolonlardan hesaplanır.
- **Grup toplamı satır olarak**: AR, `group_by_party` ile müşteri değişimini yakalar, önceki müşterinin alt toplam satırını (`bold` bayrağıyla) ve ardından boş ayırıcı satır basar; sonda "Total" satırı. Alt toplam, "para kolonları" listesinin üzerinden toplanır — bu yüzden toplam alınacak her yeni kolon o listeye eklenmelidir.
- **Sıfır ayıklama**: stok bilançoda hem hareketi hem bakiyesi sıfır olan item-depo satırı varsayılan olarak atılır.
- **Canvas'ta değil veride toplama**: toplamlar Python'da yapılır, şablon sadece biçimlendirir.

## 5. Django karşılığı için öneriler

- **Filtre sınıfı tek yerde** (django-filters/Form): tarih aralığı, çoklu seçimler, bayraklar. View: `GET` → sorgu → `columns` listesi (etiket, alan, tip, hizalama) → `rows`. Aynı `columns` + `rows` çifti hem HTML tabloya hem CSV'ye verilir (`csv.writer`, `StreamingHttpResponse`, BOM'lu UTF-8).
- **Kolonları filtreye göre üret**: `build_columns(filters)`; template kolon listesini döngüyle çizer, hazır tablo yazmaz.
- **Toplam**: ya QuerySet'te tek `aggregate()` ya da satır üretirken Python'da akümülatör; grup toplamları rapor üretiminde "bold/group" bayraklı satır olarak eklenir.
- **Etiket haritası**: `fieldname → (label, type)`; CSV başlığı da buradan gelir, iki yerde tanımlanmasın.

## 6. Tuzaklar

- **N+1**: satır başına müşteri/ürün adı çekmek. Çözüm: `select_related` / tek `values()` ile join, ya da ID→sözlük ön yükleme (ERPNext de cari detaylarını ve ürün detaylarını önceden sözlüğe alır).
- **Büyük tablo**: ledger satırlarını belleğe tamamen almama; ERPNext server-side imleç (unbuffered cursor / iterator) kullanır. Django'da `.iterator(chunk_size=...)`, açık `values()`, `only()`.
- **Sütunlarda Python toplamı vs SQL toplamı**: büyük hacimde `Sum()` SQL'de yapılmalı.
- **Tarih aralığı**: raporlar tarihi gün bazında filtreler; defter tarih-saat ile sıralanır ve aynı gün içi sıra `creation` ile bozulur. Django'da `datetime` alanını `[gün 00:00, gün+1 00:00)` aralığıyla kes; `Date` alanıyla `<=` karşılaştırması yapma. `from_date > to_date` mutlaka hata versin.
- **Açılış bakiyesi**: dönemin ilk satırıdır; "önceki tüm hareketleri topla" yaklaşımı her sorguda tüm geçmişi tarar — kapanış bakiyesi tablosu (snapshot) tut.
- **Sıfır/yuvarlama**: kayan nokta toleransı (1/10^kural) ile "outstanding var mı" kararı verilir; `!= 0` karşılaştırması gürültü satır üretir.
- **Aynı satırı iki kez sayma**: kapanış bakiyesi + defter hareketleri çakışması (ERPNext bir bayrakla açılış sorgusunu başlatır).

## 7. Kaynak

| Konu | Dosya | Satır |
|---|---|---|
| SB kolonlar | `erpnext/stock/report/stock_balance/stock_balance.py` | 649–784 |
| SB filtreler | `erpnext/public/js/stock_balance_report.js` | 1–145 |
| SB akış/toplamlar | `stock_balance.py` | 83–100, 444–474, 983–1012 |
| SB rapor tanımı | `stock_balance.json` | 1–34 |
| SB snapshot | `stock_balance_snapshot.py` | 1–60, 122–165 |
| AR kolonlar | `erpnext/accounts/report/accounts_receivable/accounts_receivable.py` | 1216–1382 |
| AR filtreler | `accounts_receivable.js` | 7–194 |
| AR grup/toplam | `accounts_receivable.py` | 101–110, 221–348, 398–415 |
| AR yaşlandırma | `accounts_receivable.py` | 819–854 |
| AR sorgu/imleç | `accounts_receivable.py` | 112–165, 856–903 |
| SL kolonlar | `erpnext/stock/report/stock_ledger/stock_ledger.py` | 312–485 |
| SL filtreler | `stock_ledger.js` | 6–129 |
| SL akış/açılış | `stock_ledger.py` | 26–152, 488–548, 744–770 |
| SL rapor tanımı | `stock_ledger.json` | 1–22 |
