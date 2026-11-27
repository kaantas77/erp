# 03 — Satış Siparişi Akışı (ERPNext incelemesi)

## 1. Durum makinesi

`status` salt-okunur ve türetilir; kullanıcı yalnızca Draft / On Hold / Closed'u elle değiştirir. Girdiler: `docstatus` + `per_delivered` + `per_billed`.

| Durum | Koşul (docstatus=1) | Kim tetikler |
|---|---|---|
| Draft | docstatus 0 | kullanıcı |
| To Deliver and Bill | `per_delivered < 100` ve `per_billed < 100` | submit, DN/SI submit/cancel |
| To Bill | `per_delivered >= 100` (veya `skip_delivery_note`) ve `per_billed < 100` | Delivery Note |
| To Deliver | `per_delivered < 100` ve `per_billed >= 100` | Sales Invoice (DN'siz fatura) |
| To Pay | `advance_payment_status == 'Requested'` | Payment Request |
| Completed | `per_delivered >= 100` ve `per_billed >= 100` | iki yüzde de dolunca |
| On Hold / Closed | kullanıcı işlemi | `update_status()` |
| Cancelled | docstatus 2 | cancel |

Submit yüzdelerle To Deliver and Bill'e geçirir; ilerledikçe To Bill / To Deliver / Completed. On Hold-Closed → Draft (re-open) mümkün, kredi limiti yeniden kontrol edilir. Closed sipariş **cancel edilemez**; önce unclose.

## 2. Stok ne zaman düşer, cari ne zaman işlenir

Sipariş **stok hareketi yaratmaz**: submit'te yalnızca rezervasyon ve `reserved_qty` güncellenir. Stok, Delivery Note submit'inde düşer. Cari Sales Invoice ile doğar; sevkiyatla cari hareket oluşmaz. Sipariş submit'i cariye sadece **kredi limiti** kontrolüyle dokunur.

## 3. Kısmi sevkiyat / faturalama izleme

İki ayrı oran ve kaynak:

- `per_delivered` = Σ min(delivered_qty, qty) / Σ qty, `skip_delivery` satırlar hariç. `delivery_status`: Not Delivered / Partly / Fully / Closed / Not Applicable.
- `per_billed` = Σ billed_amt / Σ amount (adet değil **tutar**). `billing_status`: Not Billed / Partly / Fully / Closed.

Sipariş satırındaki `delivered_qty`, `billed_amt`, `returned_qty` DN/SI'dan geri beslenir; evraklar `so_detail` bağıyla toplanır, sipariş sevkiyat listesi tutmaz.

## 4. Bizim model için öneriler ve riskler

Basit `Order: draft/confirmed/shipped/cancelled`, stok **onayda** düşüyor.

- `shipped` durumunu sevkiyat nesnesinden türet; order'da `shipped_qty` ve `billed_amount` tutup durumu bunlardan hesapla, tek "status" alanına elle yazma.
- Rezervasyon ile düşümü ayır: onayda `reserved`, sevk irsaliyesinde gerçek çıkış. Yoksa sevk edilmemiş mal stoktan yanlış düşer, iade/sayım tutmaz.
- Bağlı sevk/fatura varken `cancelled`'a geçişi reddet.
- Yüzdeleri olay anında artırma, toplamdan yeniden hesapla (cancel sonrası kaymasın).

## 5. Tuzaklar

- Yüzdeler **adet/tutar karışımı**: `per_delivered` adet, `per_billed` tutar — indirim eşit dağılmadıysa "tam sevk, eksik fatura" şaşırtır.
- Tamamlanma eşiği 100 değil ~99.999999; kayan nokta.
- Hizmet satırları (`skip_delivery`) `per_delivered`'ı 100 yapar; `per_billed` ayrıdır.
- Kapalı satırlar orandan hariç tutulur → satırı kapatmak "Completed"e zıplatabilir.
- Rezervasyon: iptal otomatik serbest bırakır, ama **kapatma** (Closed / satır kapatma) rezervasyon varken engellenir — önce elle unreserve.

## 6. Kaynak

- `.../sales_order/sales_order.json`: `status` seçenekleri 1272-1289; `delivery_status` 1290-1301; `per_delivered` 1302-1317; `per_billed` 1324-1339; `billing_status` 1340-1351.
- `.../sales_order/sales_order.py`: status tipi 174-185; `on_submit` 580-601; `on_cancel` 603-633; `check_nextdoc_docstatus` 657-670; `set_skip_delivery`/`set_delivery_progress` 399-426; `update_status` endpoint 905-914.
- `.../services/status.py`: `update_status` 30-52; yüzde güncelleme 77-106; `set_indicator` 173-186.
- Yardımcı: `erpnext/controllers/status_updater.py` Sales Order durum haritası 62-87, `COMPLETE_PERCENTAGE` 14.

> Lisans notu: GPLv3 kaynaktan yalnızca kavramsal özet; 5 satır sınırı korunmuştur.
