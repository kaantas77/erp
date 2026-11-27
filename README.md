# Depo ERP

Depo sayımı ve mutabakatı merkezli, sade bir ERP. Django 5.2, SQLite, sunucu taraflı
HTML (npm yok). Türkçe arayüz.

## Ne var?

- **Stok / Depo**: ürün, kategori, depo, stok hareketleri, mevcut stok
- **Sayım**: depo sayımı açma, sayılan miktar girişi, kapatınca otomatik fark hareketi
- **Cari**: müşteri/tedarikçi, borç-alacak defteri, tahsilat/ödeme, ekstre
- **Sipariş**: onayda rezervasyon, sevk edince stok çıkışı
- **Fatura**: satış/alış, iskonto + KDV, kesince cariye işleme, iptalde ters kayıt
- **Raporlar**: dashboard, stok bilançosu, cari bakiyeler, satış, sayım farkları, CSV

Plan ve tasarım kararları: [docs/YOL-HARITASI.md](docs/YOL-HARITASI.md)

## Kurulum

```bash
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

Açılış: <http://127.0.0.1:8000/>

## Test ve kontrol

```bash
make test    # sadece testler
make lint    # ruff check + format kontrolu
make format  # bicimlendir
make check   # hepsi: lint + format + migration + django check + testler
```

### Push öncesi otomatik kontrol

Depoyu indirdikten sonra bir kez:

```bash
git config core.hooksPath .githooks
```

Bundan sonra her `git push` öncesi `make check` ile aynı kontroller koşar; hata varsa
push durur. Kaldırmak için `git config --unset core.hooksPath`.

> GitHub Actions bu hesapta faturalama kilidi nedeniyle çalışmıyor. `.github/workflows/ci.yml`
> hazır bekliyor; aynı adımlar yerelde `make check` ile koşuyor.

## Ortam değişkenleri

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `DJANGO_SECRET_KEY` | dev anahtarı | üretimde zorunlu |
| `DJANGO_DEBUG` | `1` | üretimde `0` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | virgülle ayrılmış |
| `ERP_DB_PATH` | `db.sqlite3` | veritabanı yolu |

`DJANGO_DEBUG=0` iken SSL yönlendirme, HSTS ve güvenli çerezler otomatik açılır.

## Lisans notu

Bu proje MIT lisanslıdır. Tasarım kararları için ERPNext'in (GPLv3) **davranışı**
incelenmiştir; kodu kopyalanmamıştır. İnceleme notları `docs/arastirma/` altındadır.
