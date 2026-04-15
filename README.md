# SNI-Spoofing

## Support the original author

Please support the original author.

**USDT (BEP20):** `0x76a768B53Ca77B43086946315f0BDF21156bF424`  
**USDT (TRC20):** `TU5gKvKqcXPn8itp1DouBCwcqGHMemBm8o`

Telegram:

* `https://t.me/projectXhttp`
* `https://t.me/patterniha`

\---

## Intellectual property and credit

**All intellectual property rights, original credit, and authorship of this software belong to the original author at: https://github.com/patterniha/**

This repository/fork does not claim authorship of the original software. It continues maintenance, fixes, documentation, and additional improvements independently.

\---

## Overview

SNI-Spoofing is a Windows-based DPI bypass tool that uses IP/TCP header manipulation together with a fake TLS ClientHello / SNI-based handshake strategy.

Since direct collaboration with the original author did not move forward, development is being continued independently in this repository/fork in order to improve stability, usability, and documentation.

\---

## Features in this version

* improved relay stability on Windows
* reduced socket and resource pressure under heavy connection churn
* configurable runtime tuning through `config.json`
* optional narrower WinDivert filtering
* improved fake-send scheduling using worker queues instead of thread-per-send
* English GUI for:

  * editing settings
  * domain scanning
  * automatic lowest-latency target selection
  * manual apply for `FAKE\\\\\\\_SNI` and `CONNECT\\\\\\\_IP`
  * start/stop runtime control
  * status and log viewing

\---

## Main files

* `main.py` — core runtime / relay / service entry point
* `fake\\\\\\\_tcp.py` — packet interception and fake TCP/TLS injection logic
* `gui.py` — desktop GUI for configuration, scanning, and runtime control
* `config.json` — runtime configuration

\---

## Recommended configuration

```json
{
  "LISTEN\\\\\\\_HOST": "127.0.0.1",
  "LISTEN\\\\\\\_PORT": 400,
  "CONNECT\\\\\\\_IP": "104.16.79.73",
  "CONNECT\\\\\\\_PORT": 443,
  "FAKE\\\\\\\_SNI": "static.cloudflareinsights.com",
  "DEBUG": false,
  "HANDLE\\\\\\\_LIMIT": 64,
  "ACCEPT\\\\\\\_BACKLOG": 128,
  "CONNECT\\\\\\\_TIMEOUT": 5,
  "HANDSHAKE\\\\\\\_TIMEOUT": 2,
  "RESOURCE\\\\\\\_PRESSURE\\\\\\\_BACKOFF": 0.5,
  "FAKE\\\\\\\_SEND\\\\\\\_WORKERS": 2,
  "NARROW\\\\\\\_WINDIVERT\\\\\\\_FILTER": true
}
```

If filter parsing or startup causes trouble on a target system:

```json
{
  "NARROW\\\\\\\_WINDIVERT\\\\\\\_FILTER": false
}
```

\---

## Run from source

```bash
pip install -r requirements.txt
python main.py
python gui.py
```

> On Windows, administrator rights are typically required for WinDivert-based execution.

\---

## Build executables

```bash
python -m PyInstaller --clean --noconfirm --onefile --console --uac-admin --name bypass --paths . --collect-binaries pydivert --hidden-import utils.network\\\\\\\_tools --hidden-import utils.packet\\\\\\\_templates main.py
python -m PyInstaller --clean --noconfirm --onefile --windowed --uac-admin --name gui --paths . gui.py
```

Keep `config.json` next to the generated executables unless your runtime path handling is changed.

\---

## Credits

* **Original author:** `patterniha`
* **Original source:** `https://github.com/patterniha/`
* **Current maintenance:** this fork

\---

# نسخه فارسی

## حمایت از نویسنده اصلی

لطفاً از نویسنده اصلی حمایت کنید.

**USDT (BEP20):** `0x76a768B53Ca77B43086946315f0BDF21156bF424`  
**USDT (TRC20):** `TU5gKvKqcXPn8itp1DouBCwcqGHMemBm8o`

تلگرام:

* `https://t.me/projectXhttp`
* `https://t.me/patterniha`

\---

## حقوق معنوی و کردیت

**کلیه حقوق معنوی، کردیت اصلی، و انتساب این نرم‌افزار متعلق به نویسنده اصلی در این نشانی است: https://github.com/patterniha/**

این ریپازیتوری/فورک ادعایی نسبت به نویسندگی نسخه اصلی نرم‌افزار ندارد و فقط نگهداری، رفع اشکال، مستندسازی، و توسعه‌های تکمیلی را به‌صورت مستقل ادامه می‌دهد.

\---

## معرفی

SNI-Spoofing یک ابزار عبور از DPI در ویندوز است که با دست‌کاری هدرهای IP/TCP و استفاده از یک handshake جعلی مبتنی بر TLS ClientHello / SNI کار می‌کند.

از آنجا که همکاری مستقیم با نویسنده اصلی به نتیجه نرسید، توسعه این پروژه در این ریپازیتوری/فورک به‌صورت مستقل ادامه داده می‌شود تا پایداری، usability، و مستندسازی آن بهتر شود.

\---

## قابلیت‌های این نسخه

* پایداری بهتر relay در ویندوز
* کاهش فشار روی socket و منابع سیستم در شرایط churn بالا
* امکان تنظیم پارامترهای runtime از طریق `config.json`
* امکان استفاده از فیلتر محدودتر WinDivert
* بهبود زمان‌بندی fake-send با worker queue به‌جای ساخت thread برای هر ارسال
* GUI انگلیسی برای:

  * ویرایش تنظیمات
  * اسکن دامین
  * انتخاب خودکار کم‌تأخیرترین گزینه
  * اعمال دستی `FAKE\\\\\\\_SNI` و `CONNECT\\\\\\\_IP`
  * اجرای سرویس و توقف آن
  * مشاهده وضعیت و لاگ‌ها

\---

## فایل‌های اصلی

* `main.py` — نقطه شروع سرویس و منطق اصلی runtime / relay
* `fake\\\\\\\_tcp.py` — منطق رهگیری packet و تزریق fake TCP/TLS
* `gui.py` — رابط گرافیکی برای تنظیمات، اسکن، و کنترل runtime
* `config.json` — فایل تنظیمات runtime

\---

## تنظیمات پیشنهادی

```json
{
  "LISTEN\\\\\\\_HOST": "127.0.0.1",
  "LISTEN\\\\\\\_PORT": 400,
  "CONNECT\\\\\\\_IP": "104.16.79.73",
  "CONNECT\\\\\\\_PORT": 443,
  "FAKE\\\\\\\_SNI": "static.cloudflareinsights.com",
  "DEBUG": false,
  "HANDLE\\\\\\\_LIMIT": 64,
  "ACCEPT\\\\\\\_BACKLOG": 128,
  "CONNECT\\\\\\\_TIMEOUT": 5,
  "HANDSHAKE\\\\\\\_TIMEOUT": 2,
  "RESOURCE\\\\\\\_PRESSURE\\\\\\\_BACKOFF": 0.5,
  "FAKE\\\\\\\_SEND\\\\\\\_WORKERS": 2,
  "NARROW\\\\\\\_WINDIVERT\\\\\\\_FILTER": true
}
```

اگر parse شدن فیلتر یا startup مشکل داشت:

```json
{
  "NARROW\\\\\\\_WINDIVERT\\\\\\\_FILTER": false
}
```

\---

## اجرا از روی سورس

```bash
pip install -r requirements.txt
python main.py
python gui.py
```

> در ویندوز، برای اجرای مبتنی بر WinDivert معمولاً دسترسی administrator لازم است.

\---

## ساخت فایل اجرایی

```bash
python -m PyInstaller --clean --noconfirm --onefile --console --uac-admin --name bypass --paths . --collect-binaries pydivert --hidden-import utils.network\\\\\\\_tools --hidden-import utils.packet\\\\\\\_templates main.py
python -m PyInstaller --clean --noconfirm --onefile --windowed --uac-admin --name gui --paths . gui.py
```

فایل `config.json` را کنار فایل‌های اجرایی نگه دار، مگر اینکه منطق مسیرهای runtime را تغییر داده باشی.

\---

## اعتبار

* **نویسنده اصلی:** `patterniha`
* **منبع اصلی:** `https://github.com/patterniha/`
* **نگهداری فعلی:** این فورک



