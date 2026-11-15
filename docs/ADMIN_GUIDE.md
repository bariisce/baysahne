# Admin Guide

## Part 1 — For the developer (account owner)

### Roles

| Role | Can do | Cannot do |
|---|---|---|
| **İçerik editörü** (editor) | Productions, posters and galleries, performances (create, cancel, reschedule), venues, announcements, media library, view notification history | Manage staff, change notification rules or templates, edit organisation or legal texts, view the audit log |
| **Yönetici** (admin) | Everything an editor can do, plus staff, notification policy and templates, job cancel/retry, organisation profile, legal texts, audit log | Nothing in the panel exposes servers, databases, deployment, Firebase, Apple/Google or SMTP credentials |

Permissions are enforced by the API. Hiding a menu item is only a convenience.

### Creating the first administrator

The system has no default account and no public sign-up. On the server (or locally):

```bash
cd backend
python -m app.cli bootstrap-admin --email <your-email> --name "<Your Name>"
```

The command prints a one-time link (valid 72 h). Open it, choose a password (≥ 10 characters) and you are signed in. The command refuses to run once an active admin exists. `--force` is a break-glass option for recovery only.

### Inviting Bay Sahne staff

The staff list (full name + e-mail) has not been provided yet. When you have it:

1. Sign in as admin → **Ekip ve erişim** → **Kişi davet et**.
2. Enter the full name, e-mail and role. Most staff should be **İçerik editörü**; make someone **Yönetici** only if they need to manage other staff.
3. They receive an e-mail (SMTP must be configured in production, see DEPLOYMENT) with a single-use link valid for 72 hours. Expired links can be re-sent from the same page.

To remove someone: **Erişimi kapat**. Their sessions end immediately; their past actions stay in the audit log. The system always keeps at least one active admin.

Forgotten passwords: staff use **Parolamı unuttum** on the login page (60-minute single-use link). A reset signs out all of that person's sessions.

In development, invitation and reset e-mails are printed to the API console (`EMAIL_BACKEND=console`) or written to `backend/var/outbox` (`file`). Neither backend is allowed in production.

## Part 2 — Personel için kılavuz (Türkçe)

### Giriş
Size gelen davet e-postasındaki bağlantıyla parolanızı belirleyin. Sonraki girişler için yönetim paneli adresini kullanın. Parolanızı unutursanız giriş sayfasındaki **Parolamı unuttum** bağlantısını kullanın.

### Oyun eklemek ve yayınlamak
1. **Oyunlar → Yeni oyun**: adı, hikâyeyi, türü, süreyi ve künyeyi (yazar, yönetmen, oyuncular…) girin. Oyun **taslak** olarak oluşturulur ve uygulamada görünmez.
2. **Afiş ve görseller** sekmesi: **Afiş ekle** ile dikey (3:4) bir afiş yükleyin. **Görsel ekle** ile oyundan kareler ekleyin, okları kullanarak sıralayın. JPEG, PNG veya WebP, en fazla 15 MB.
3. **Önizleme** sekmesinde uygulamadaki görünümü kontrol edin.
4. **Yayınla**. Oyun ilk kez yayınlanıyorsa “Yeni oyun bildirimi gönder” seçeneği çıkar. İşaretlerseniz bildirim izni veren herkese **bir kez** gider; aynı oyun için tekrar gönderilmez.
5. Artık oynanmayan bir oyunu silmeyin, **Arşivle**. Geçmiş temsilleri korunur ve oyun uygulamadan kalkar.

“Sahnede” işareti yalnızca bir etikettir. Uygulamada tarih göstermek için mutlaka **temsil** ekleyin.

### Program (temsiller)
- **Program / Temsiller → Temsil ekle**: oyun, salon, tarih ve saat girin. Saat, salonun yerel saatidir (Türkiye). “Hemen yayınla” işaretliyse temsil uygulamada görünür ve hatırlatma bildirimi (varsayılan: 24 saat önce) otomatik planlanır.
- Aynı salonda veya aynı oyun için yakın saatte başka bir temsil varsa sistem uyarır. Kontrol edip yine de kaydedebilirsiniz.
- **Tarih değiştir**: yayınlanmış bir temsilin tarihi yalnızca bu yolla değişir. Seyirciye “Yeni tarih” bildirimi gider ve eski hatırlatma iptal edilir.
- **İptal et**: temsil uygulamada “İptal edildi” olarak görünür (silinmez). İsterseniz seyirciye kısa bir açıklama yazın. Temsil daha önce duyurulduysa “Program değişikliği” bildirimi bir kez gönderilir.
- **Yayından kaldır** seyirciye bildirim göndermez. Seyirciyi bilgilendirmek istiyorsanız **İptal et**’i kullanın.

### Salonlar, duyurular, görseller
- **Salonlar**: adres, harita bağlantısı ve ulaşım notları. Temsili olan bir salon silinemez; **pasif** yapılabilir.
- **Duyurular**: başlık, metin ve isteğe bağlı görsel. Taslak olarak kaydedilir; listeden yayınlanır.
- **Görseller**: tüm yüklenen görseller. Bir afişte veya galeride kullanılan görsel silinemez.

### Bildirimler (yöneticiler)
**Bildirimler** sayfasında hatırlatma süresi (ör. `24` veya `24, 3` saat), cihaz başına günlük üst sınır ve bildirim metinleri düzenlenir. Metinlerde yalnızca listelenen alanlar kullanılabilir (ör. `{title}`, `{date}`, `{time}`, `{venue}`). **Önizle** ile metni kontrol edin. **Gönderim geçmişi**, her bildirimin kaç cihaza iletildiğini ve hataları gösterir. Bildirimler, izin veren cihazlara gider; her cihaza ulaşacağı garanti edilemez.
