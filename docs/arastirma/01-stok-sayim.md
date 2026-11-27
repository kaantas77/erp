# Stok Sayımı (Stock Reconciliation) — ERPNext İncelemesi

## 1. Nasıl çalışıyor

Belge, sayımın **hedefini** yazar: satır başına sayılan miktar (`qty`) ve birim değer (`valuation_rate`). Sistem sayım anındaki (posting tarih/saati) mevcut bakiyeyi ayrı alanlara doldurur (`current_qty`, `current_valuation_rate`). Fark = yeni tutar − mevcut tutar. Geçmiş hareketler silinmez; yalnızca bu fark kadar yeni stok defteri kaydı yazılır, yani defter hedefe taşınır. Fark, stok hesabı ile bir fark hesabı arasına muhasebeleşir; değişmeyen satır atılır.

## 2. Alanlar

Ana belge: `company` (Link, şirket), `purpose` (Select: Opening Stock / Stock Reconciliation / Adjustment Entry), `posting_date`+`posting_time` (Date/Time, sayım anı), `set_posting_time` (Check, geçmiş tarihe izin), `items` (Tablo, zorunlu), `expense_account` (Link, fark hesabı), `cost_center` (Link), `difference_amount` (Para, salt okunur toplam fark), `set_warehouse` (Link, varsayılan depo), `scan_mode` (Check, mevcut miktarı çekmeyi kapatır), `naming_series`, `amended_from`.

Satır: `item_code`, `warehouse` (Link), `qty` (Sayı, hedef miktar), `valuation_rate` (Para, hedef birim değer), `amount` (Para), `current_qty`/`current_valuation_rate`/`current_amount` (salt okunur, önceki durum), `quantity_difference` (salt okunur), `amount_difference` (Para, deftere yazılan değer farkı), `allow_zero_valuation_rate` (Check), `serial_no`/`batch_no`, `reconcile_all_serial_batch` (Check), `stock_uom`.

## 3. Akış adımları

1. Amaç seçilir: adet farkı için "Stock Reconciliation", değer farkı için "Adjustment Entry", açılış için "Opening Stock".
2. Doğrulama: aynı ürün+depo tekrarı, negatif miktar/fiyat yasağı, miktar veya fiyattan en az birinin girilmiş olması, stok kalemi kontrolü.
3. Fiyat boşsa mevcut değerleme fiyatı, o da yoksa alış fiyatı / ürün varsayılanı kullanılır.
4. Mevcut durum okunur, değişmeyen satırlar atılır; hepsi değişmediyse hata.
5. Fark hesaplanır: yeni tutar − mevcut tutar (satır ve toplam).
6. Onayda mevcut miktar düşülür, yeni miktar eklenir; defter bakiyesi ve stok değeri yeniden hesaplanır.
7. Muhasebe: stok hesabı ↔ `expense_account`, `cost_center` ile.
8. İleri tarihli hareketler etkilenirse yeniden değerleme (repost) kuyruğa alınır.
9. İptalde karşıt kayıtlar yazılır; parti/seri paketleri ve otomatik kayıtlar geri alınır.
10. 100 satırdan fazla belge arka plan işine devredilir.

## 4. Projemiz için: al / atla

**Al:** hedef + mevcut çift alan modeli; farkı tutar bazında hesaplama; silmek yerine hareket yazma; satır bazında defter = hedef miktar/tutar; değişmeyen satırı atma; negatif ve tekrar yasakları; iptal = karşıt hareket; onaylanan kaydın değişmezliği.

**Atla:** seri/parti paketleri, depo ağacı, envanter boyutları, standart maliyet, müşteri tedariki, rezerve stok, ağır repost motoru. Basit sürümde tek depo ve ortalama maliyet yeterli; yeniden değerlemeyi rapor sırasında hesaplayarak ertele.

## 5. Tuzaklar

- Farkı, `current_qty`'yi kayıt anında yeniden okuyarak hesaplamak: geçmiş tarihli kayıt araya girince sonuç kayar.
- Miktar farkını sıfır fiyatla yazmak değer kaybettirir; boş fiyat ("koru") ile açık `0` ("sıfırla") ayrılmalı.
- Geçmiş tarihli sayım sonraki hareketleri geçersiz kılar (eksi stok) → repost şart.
- İptalde farkı yeniden hesaplamak; iptal, kaydetme anındaki tutarı aynen tersine çevirmeli.
- Aynı ürün+depo için çok satır, birim (UOM) dönüşümü, negatif stok izni.

## 6. Kaynak

`erpnext-develop/erpnext/stock/doctype/stock_reconciliation/stock_reconciliation.py`
- 84–140 doğrulama; 156–170 onay; 239–261 iptal
- 728–828 değişmeyen satır + fark; 830–921 satır kontrolleri
- 1012–1090 ve 1146–1238 defter (SLE); 1240–1257 iptal defteri
- 1287–1315 muhasebe; 1374–1383 toplamlar; 1384–1500 repost sonrası senkron
- 1541–1566 kuyruk; 1825–1839 satır değer farkı; 1842–1997 bakiye okuma

`.../stock_reconciliation.json` 1–232 (ana alanlar; 204 `is_submittable`), `.../stock_reconciliation_item.json` (satır alanları). Repost tetiği: `erpnext/stock/services/stock_ledger_service.py` 219–260.
