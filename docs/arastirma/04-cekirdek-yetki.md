# 04 — Çekirdek: Numaralandırma, Yaşam Döngüsü, Yetki ve Onay

> Lisans notu: ERPNext (GPLv3) kaynağından kod kopyalanmadı; yalnızca kavram özeti. Kod bloğu yok.

## 1. Numaralandırma

Belge adı, içerikten değil **şablondan** üretilir. Kalıcı açılışta hesaplanan bir "önek + değişken + ayırıcı" dizisi, sıra numarasıyla birleşir. Hazır değişkenler takvim ve şirket bilgisidir: mali yıl, tam/yarım mali yıl, ay, gün, yıl, hafta, yılın günü ve **şirket kısaltması (abbr)**. Kısaltma, şirket adındaki kelimelerin ilk harflerinden otomatik türetilir ve şirketler arasında tekil olmak zorundadır.

Üç ayrıntı önemli. Birincisi, şablon alanı **salt bir kez** yazılabilir; sonradan seriyi değiştirmek geçmiş numaralandırmayı bozar. İkincisi, numara **taslakta** üretilir — submit beklemez; yani "taslak fiş" de numara taşır ve numara boşluğu (iptal, silme) meşru sayılır. Üçüncüsü, şirket düzeyindeki tek "series" kavramı belge içi seri değildir: şirket, kısaltmanın sahibi ve tekilliğinin garantörüdür (kontrol `validate_abbr`). Seri seçenekleri her DocType'ın kendi tanımında durur; dönen sabitler şablonu değiştirmeden, açılışta tek yerden sağlanır.

Django'nun `AutoField`'ine göre fark: kullanıcıya anlamlı, şirket/yıl ayrıştırılabilir, sıralanabilir bir dize. Bizde de numara ayrı bir "sequence" tablosundan değil, **şablon + kilitli sayaç** ile ve taslakta üretilmeli.

## 2. Yaşam döngüsü (submit / cancel / amend) ve bize etkisi

Üç durum var: **0 taslak** (serbestçe düzenlenir, silinebilir), **1 onaylı/kayıtlı** (muhasebe ve stok hareketi doğar, artık düzenlenemez; yalnızca sınırlı alanlar sonradan değişebilir), **2 iptal** (kayıt silinmez, kaydın etkisi **ters kayıtla** geri alınır; belge iz olarak kalır).

Submit sırasında işi "doğrula → yaz → yay" sırasına dizmek kritik: hazırlık kontrolü (ör. borç = alacak), asıl kayıt yazımı, ardından yan etkiler (bağlı belgeler, kredi limiti, karşı belge). İptalde aynı yan etkilerin tersi ve bağlantıların çözülmesi gerekir; ayrıca iptal inceliği var: büyük belgelerde iptal **arka plana** kuyruklanır, banka mahsup tarihi gibi kopyalanan alanlar temizlenir. Amend ise "iptal edilmiş belgenin düzeltilmiş kopyası": kaynak bağlantısı taşır, **yeni numara** alır, taslak olarak başlar ve öncekinin satır bazlı iptal kararlarını (ör. "kapatıldı" işaretleri) taşımaz.

Bizim "status + cancelled" yaklaşımına kattığı: (i) **kayıt silme yok** — iptal, satırın olumsuz ikizidir; denetim izi bozulmaz. (ii) Düzenlenebilir/düzenlenemez sınırı `status` alanına değil, ayrı bir "kesinleşti mi" alanına bağlanır; yoksa biri kayda statüyü elle geri alarak muhasebeyi bozar. (iii) İptal sonrası düzeltme, aynı belgeyi yeniden açmak değil, **bağlı yeni bir belge** üretmektir (`replaced_by`). Ondan sonra kapanış/tamamlanma durumu yine türetilmiş kalır.

## 3. Yetki modeli, Django'ya sadeleştirilmiş hali

ERPNext üç katman kullanır: **rol tabanlı DocType izinleri** (kim okur/yazar/onaylar/siler — varsayılan: olumsuz, açıkça verilir), **satır düzeyi filtre** ("sorgu koşulu"na eklenen kısıt, ör. sadece kullanıcının şirketi) ve nesne düzeyi karar. Görünürlük için de aynı kısıt hem liste hem tek-kayıt tarafında uygulanmalıdır; tek tarafa koymak sızıntıdır.

Django karşılığı en yalın hali: `Group` = rol. Modele `Meta.permissions` ile `view/add/change/approve/cancel` gibi eylem izinleri tanımla, ama `auth.Permission`'ı **DocType × eylem** düzeyinde tut; satır bazlı sahiplik için `company`/`branch` alanını `Organization` modeline bağla ve `get_queryset()`'te filtreyi tek yerden uygula. Kritik kural: silme yalnızca taslakta; iptal ayrı bir izin (`cancel_*`). Onay da ayrı: kayıt edebilen herkes onaylayamamalı.

## 4. Onay / kontrol noktaları

İncelenen noktalar, hepsi "sınır aşımı" deseninde: **kontrol, engelleme değil rol tabanlı istisna**. Fazla teslim/fazla fatura için yüzde tolerans tanımlanır (genel ayar veya ürün bazında); aşım tolere ediliyorsa kimse durmaz, aşıyorsa ya hata atılır ya da **yetkili rolde** olan kullanıcı yalnızca uyarı görüp devam eder. Aynı desen cari kredi limitinde: limitin aşılması kimseye "yok" demez — limiti yükseltecek sorumluya yönlendirir. Bağlı belgelerin miktar/tutar yüzdeleri de onay/iptal olaylarında yeniden hesaplanır.

Basit ERP'de onay **ne zaman** gerekir: (1) nakit/GL etkisi doğuran belgelerde, (2) cari limitin aşılmasında, (3) sipariş edilenden fazla çıkış/faturada, (4) fiyat/iskonto eşiği altında satışta. Ne zaman **gerekmez**: tek kullanıcı, tek şirket, düşük hacim — orada onay sadece gecikme yaratır. Kural: onay "durum" olmamalı, **belge düzeyinde bir karar kaydı** olmalı (kim, ne zaman, hangi gerekçeyle).

## 5. Tuzaklar

- Numara taslakta üretilir; "silinen taslak" numara boşluğu bırakır. Denetimde boşluk normaldir; bunu hata sanıp sıra numarası yeniden kullanmak çift numara üretir.
- Seri alanını sonradan düzenlenebilir bırakmak; geçmiş numaralandırma geriye dönük bozulur.
- Tek "status" alanına hem düzenlenebilirlik hem iş akışı yüklemek: kayda elle statü yazmak kesinleşmiş kaydı düzenlenebilir yapar.
- İptal = silme sanmak. Kaydı silmek denetim izini, bağlı belge bağlarını ve numara tekilliğini bozar.
- Amend'de önceki belgenin satır kararlarını (kapatma, mahsup tarihi, referanslar) kopyalamak; yeni belge "zaten yapılmış" gibi davranır.
- İptali senkron varsaymak; yan etkileri (bağlı belgeler) geri almadan statüyü "cancelled" yazmak.
- Satır düzeyi yetki filtresini yalnız listede uygulamak.
- Tolerans/yuvarlama eşiklerini kayan nokta ile `>= 100` karşılaştırmak; tamamlanma %99.999999'u geçince dolmuş sayılır.
- Rol adlarını koda gömmek; ayardan değiştirilebilir rol (ör. "kredi sorumlusu") boş kalınca kontrol sessizce devre dışı kalır.
- Kısmi veri ile "onay" akışı kurup onaydan sonra da kaydı düzenlemeye izin vermek.

## 6. Kaynak: dosya yolu + satır aralıkları

- `erpnext/controllers/status_updater.py`: `COMPLETE_PERCENTAGE` 14; `validate_status` 21-23; `StatusUpdater` 207; `on_discard` 215-217; `update_prevdoc_status` 219-222; kapalı satır kontrolü 247-285; `set_status` 287-306; `get_status` 308-353; tolerans kontrolü 551-599; limit hatası 601-648; rol ile devam 650-665; `update_qty` 667-688; hedef satır güncelleme 690-759; yüzde hesabı 761-811; tamamlanma eşiği 813-825; yüzde alanı güncelleme 845-878.
- `erpnext/hooks.py`: lisans başlığı 8; `permission_query_conditions` 352-372; `has_permission` 374-394; `has_website_permission` 396-407; `period_closing_doctypes` 410-429; `doc_events` 433-510; adlandırma değişkenleri 512-516; `auto_cancel_exempted_doctypes` 518-532.
- `erpnext/setup/doctype/company/company.py`: `abbr` alanı 46; `validate_abbr` 363-373 (tekillik `frappe.db.exists` 372); `depreciation` seri alanı 137; `abbreviate` 967-968; `get_name_with_abbr` 1064-1071.
- `erpnext/accounts/doctype/journal_entry/journal_entry.py`: `validate` 142-188; `before_cancel` 223-227; `cancel` (arka plan kuyruğu) 229-234; `before_submit` (denge kontrolü, içe aktarımda atlanır) 236-240; `on_submit` (GL yazımı ve yayılım) 242-254; `on_update_after_submit` 327-336; `on_cancel` (ters kayıt + bağlantı çözme) 338-373; `check_credit_limit` 530-546.
- `erpnext/accounts/doctype/journal_entry/journal_entry.json`: `autoname` 5; `naming_series` 117-127; `amended_from` 497-508; `amend` bayrakları 692, 706.
- Destek: `erpnext/accounts/doctype/sales_invoice/services/status.py` 12-30; `erpnext/controllers/accounts_controller.py` 127-146; `erpnext/controllers/item_close.py` 132-144; `erpnext/selling/doctype/customer/customer.py` 628-675.
