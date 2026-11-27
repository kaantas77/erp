# ERP Yol Haritası — ERPNext referansıyla

Bu doküman, ERPNext (develop, GPLv3) kaynağının **kavramsal** incelenmesinden çıkan
kararları ve kendi projemizin planını içerir. ERPNext kodu **kopyalanmamıştır**;
sadece davranış, alan listesi ve iş akışı düzeyinde faydalanılmıştır.
Ayrıntılı notlar: `docs/arastirma/01..05`.

## 0. Lisans sınırı

| Yapılabilir | Yapılmaz |
|---|---|
| Kavram, iş akışı, alan adı öğrenmek | Kod satırı kopyalamak |
| "Şu raporda şu kolonlar var" bilgisi | Değişken adı değiştirilmiş kopya |
| Durum makinesini kendi tasarımımızla yazmak | ERPNext dosyalarını repoya almak |

Bizim proje MIT. Notlar `docs/arastirma/` altında kanıt olarak duruyor.

## 1. Alınan 6 temel karar

### K1 — Stok fiziksel olarak sevkte düşer, siparişte değil
ERPNext'te sipariş stok hareketi yaratmaz; rezervasyon yazar, çıkışı irsaliye yapar.
**Bizde de öyle:** `confirm_order` → `OrderReservation` (rezerve), `mark_shipped` → `StockMove(-qty)`.
*Sebep:* bizim ürünün asıl derdi depo sayımı. Onayda stok düşerse, sevk edilmemiş mal
"kâğıt üstünde yok, rafta var" farkına dönüşür ve sayımı kirletir.

### K2 — Silme yok, ters kayıt var
Fatura iptali kaydı silmez; ters yönlü `LedgerEntry` yazar, belge durumu `cancelled` olur.
ERPNext'te de iptal = karşıt kayıt. Bakiye her zaman `Σborç − Σalacak`.

### K3 — Bakiye/stok kolonda tutulmaz, hesaplanır
`Product.stock_qty` gibi bir kolon yok; `Sum(moves.quantity)` ile bulunur. Aynı şekilde
cari bakiye `Sum(debit-credit)`. *Sebep:* iki yerde tutulan sayı er geç birbirini tutmaz.

### K4 — Sayımda "sistem miktarı" sayım anında dondurulur
`CountLine.system_qty` açılışta yazılır, sonradan okunmaz. Fark = `counted - system`.
ERPNext de belge açılışında `current_qty`'yi dondurur.

### K5 — Belge numarası `PREFIX-YIL-SIRA`
`SIP-2026-0001`, `SF-2026-0001`, `SAY-2026-001`. Taslakta üretilir; boşluk (silinen
taslak) normaldir. ERPNext'in naming series mantığının sade hali.

### K6 — Durum alanı tek iş yapsın
`status` (draft/confirmed/shipped/cancelled) iş akışını anlatır; "düzenlenebilir mi"
sorusu `is_editable` property'si ile türetilir. ERPNext'in `docstatus` + türetilmiş
`status` ayrımının sadeleşmiş hali.

## 2. Modül durumu (bu PR)

| Modül | Durum | Not |
|---|---|---|
| Depo / Stok / Sayım | ✅ çalışıyor | sayım aç, say, kapat, fark hareketi |
| Cari (bakiye, tahsilat, ekstre) | ✅ çalışıyor | borç/alacak defteri |
| Sipariş (rezervasyon + sevk) | ✅ çalışıyor | onay = rezerve, sevk = stok çıkışı |
| Fatura (satış/alış, KDV, cari) | ✅ çalışıyor | iptal = ters kayıt |
| Dashboard + CSV raporları | ✅ çalışıyor | stok, cari, satış |
| Yetki/rol (Django groups) | ⬜ sonraki PR | K6 sonrası kolay |
| Satın alma (PO → mal kabul) | ⬜ sonraki PR | şimdilik alış faturası yeter |
| Kısmi sevkiyat / irsaliye | ⬜ sonraki PR | şu an tek seferde sevk |
| Teklif, sipariş onay akışı | ⬜ ertelendi | tek kullanıcıda gereksiz |

## 3. Sıradaki işler (öncelik sırası)

1. **Yetki**: `Group` = rol (Depo, Muhasebe, Yönetici), `Meta.permissions` ile
   `approve`/`cancel` ayrı izin, tüm `get_queryset()` tek yerden filtre (not: 04-cekirdek-yetki).
2. **İrsaliye**: sevkiyatı ayrı belge yapmak; kısmi sevkiyat için `delivered_qty` takibi.
   Not 03'teki `per_delivered`/`per_billed` deseninin sade hali.
3. **Kısmi fatura**: sipariş → fatura kalemi eşleşmesi (`billed_amount`).
4. **Yaşlandırma raporu**: 0-30/31-60/61-90/90+ (not: 05-raporlama, `ageing_based_on`).
5. **Excel dışa aktarma**: CSV var, `.xlsx` (openpyxl) eklenecek.

## 4. Bilerek yapmadıklarımız

| ERPNext'te var | Bizde yok | Neden |
|---|---|---|
| DocType/meta-driven yapı | Django modelleri | küçük ekip, tip güvenliği |
| Commit başına stok defteri (SLE) | hareket tablosu | aynı işi sade yapar |
| Ortalama/standart maliyet motoru | alış fiyatı | değerleme raporu sonra |
| Seri/parti, depo ağacı | tek seviye depo | MVP kapsamı |
| Repost (geçmiş tarihli düzeltme) | yok | sayımlar bugün için |
| Amend (yerine yeni belge) | iptal + yeniden kes | sade akış |

## 5. Test stratejisi

`pytest` + `pytest-django`, SQLite. Kapsanan kritik davranışlar:
- stok hesabı (giriş/çıkış/negatif)
- sayım: sistem miktarı dondurma, fark hareketi, sayılmadan kapatma engeli
- sipariş: onayda stok düşmemesi, çifte rezervasyon engeli, sevk
- fatura: KDV/iskonto hesabı, cari borçlanma, iptal ters kayıt
- sayfalar: login zorunluluğu, dashboard, sayım açma akışı

CI: GitHub Actions, `ruff check` + `ruff format --check` + `makemigrations --check` +
`manage.py check --deploy` + `pytest`.
