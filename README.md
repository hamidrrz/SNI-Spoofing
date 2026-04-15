# SNI-Spoofing

## Support the original author

Please support the original author.

**USDT (BEP20):** `0x76a768B53Ca77B43086946315f0BDF21156bF424`  
**USDT (TRC20):** `TU5gKvKqcXPn8itp1DouBCwcqGHMemBm8o`

Telegram:
- `https://t.me/projectXhttp`
- `https://t.me/patterniha`

---

## Intellectual property and credit

**All intellectual property rights, original credit, and authorship of this software belong to the original author at: https://github.com/patterniha/**

This repository/fork does not claim authorship of the original software. It continues maintenance, fixes, documentation, and additional improvements independently.

---

## Overview

SNI-Spoofing is a Windows-based DPI bypass tool that uses IP/TCP header manipulation together with a fake TLS ClientHello / SNI-based handshake strategy.

Since direct collaboration with the original author did not move forward, development is being continued independently in this repository/fork in order to improve stability, usability, and documentation.

---

## Features in this version

- improved relay stability on Windows
- reduced socket and resource pressure under heavy connection churn
- configurable runtime tuning through `config.json`
- optional narrower WinDivert filtering
- improved fake-send scheduling using worker queues instead of thread-per-send
- English GUI for:
  - editing settings
  - domain scanning
  - automatic lowest-latency target selection
  - manual apply for `FAKE_SNI` and `CONNECT_IP`
  - start/stop runtime control
  - status and log viewing

---

## GUI

The repository includes a desktop control panel in `gui.py`.

### What the GUI does

- loads and saves `config.json`
- allows direct editing of:
  - `LISTEN_HOST`
  - `LISTEN_PORT`
  - `CONNECT_IP`
  - `CONNECT_PORT`
  - `FAKE_SNI`
  - `DEBUG`
  - `HANDLE_LIMIT`
  - `ACCEPT_BACKLOG`
  - `CONNECT_TIMEOUT`
  - `HANDSHAKE_TIMEOUT`
  - `RESOURCE_PRESSURE_BACKOFF`
  - `FAKE_SEND_WORKERS`
  - `NARROW_WINDIVERT_FILTER`
- provides a domain scanner that:
  - accepts one domain per line
  - resolves IPv4 addresses
  - measures ping/latency
  - shows scan results in a table
  - auto-selects the best result
  - lets the user manually apply a selected result
- updates `FAKE_SNI` and `CONNECT_IP` based on the selected domain result
- provides runtime controls:
  - `RUN`
  - `STOP`
  - `Clear log`
- shows runtime information:
  - service status
  - proxy endpoint
  - current target
  - launch source
  - live service log

### GUI usage

Run the GUI:

```bash
python gui.py
```

If `bypass.exe` exists next to the GUI, it can be used as the launch target. Otherwise the GUI can run the Python source directly, depending on the local setup.

---

## Main files

- `main.py` — core runtime / relay / service entry point
- `fake_tcp.py` — packet interception and fake TCP/TLS injection logic
- `gui.py` — desktop GUI for configuration, scanning, and runtime control
- `config.json` — runtime configuration

---

## Recommended configuration

```json
{
  "LISTEN_HOST": "127.0.0.1",
  "LISTEN_PORT": 400,
  "CONNECT_IP": "104.16.79.73",
  "CONNECT_PORT": 443,
  "FAKE_SNI": "static.cloudflareinsights.com",
  "DEBUG": false,
  "HANDLE_LIMIT": 64,
  "ACCEPT_BACKLOG": 128,
  "CONNECT_TIMEOUT": 5,
  "HANDSHAKE_TIMEOUT": 2,
  "RESOURCE_PRESSURE_BACKOFF": 0.5,
  "FAKE_SEND_WORKERS": 2,
  "NARROW_WINDIVERT_FILTER": true
}
```

If filter parsing or startup causes trouble on a target system:

```json
{
  "NARROW_WINDIVERT_FILTER": false
}
```

---

## Run from source

```bash
pip install -r requirements.txt
python main.py
python gui.py
```

> On Windows, administrator rights are typically required for WinDivert-based execution.

---

## Build executables

```bash
python -m PyInstaller --clean --noconfirm --onefile --console --uac-admin --name bypass --paths . --collect-binaries pydivert --hidden-import utils.network_tools --hidden-import utils.packet_templates main.py
python -m PyInstaller --clean --noconfirm --onefile --windowed --uac-admin --name gui --paths . gui.py
```

Keep `config.json` next to the generated executables unless your runtime path handling is changed.

---

## Credits

- **Original author:** `patterniha`
- **Original source:** `https://github.com/patterniha/`
- **Current maintenance:** this fork

---

# نسخه فارسی

## حمایت از نویسنده اصلی

لطفاً از نویسنده اصلی حمایت کنید.

**USDT (BEP20):** `0x76a768B53Ca77B43086946315f0BDF21156bF424`  
**USDT (TRC20):** `TU5gKvKqcXPn8itp1DouBCwcqGHMemBm8o`

تلگرام:
- `https://t.me/projectXhttp`
- `https://t.me/patterniha`

---

## حقوق معنوی و کردیت

**کلیه حقوق معنوی، کردیت اصلی، و انتساب این نرم‌افزار متعلق به نویسنده اصلی در این نشانی است: https://github.com/patterniha/**

این ریپازیتوری/فورک ادعایی نسبت به نویسندگی نسخه اصلی نرم‌افزار ندارد و فقط نگهداری، رفع اشکال، مستندسازی، و توسعه‌های تکمیلی را به‌صورت مستقل ادامه می‌دهد.

---

## معرفی

SNI-Spoofing یک ابزار عبور از DPI در ویندوز است که با دست‌کاری هدرهای IP/TCP و استفاده از یک handshake جعلی مبتنی بر TLS ClientHello / SNI کار می‌کند.

از آنجا که همکاری مستقیم با نویسنده اصلی به نتیجه نرسید، توسعه این پروژه در این ریپازیتوری/فورک به‌صورت مستقل ادامه داده می‌شود تا پایداری، usability، و مستندسازی آن بهتر شود.

---

## قابلیت‌های این نسخه

- پایداری بهتر relay در ویندوز
- کاهش فشار روی socket و منابع سیستم در شرایط churn بالا
- امکان تنظیم پارامترهای runtime از طریق `config.json`
- امکان استفاده از فیلتر محدودتر WinDivert
- بهبود زمان‌بندی fake-send با worker queue به‌جای ساخت thread برای هر ارسال
- GUI انگلیسی برای:
  - ویرایش تنظیمات
  - اسکن دامین
  - انتخاب خودکار کم‌تأخیرترین گزینه
  - اعمال دستی `FAKE_SNI` و `CONNECT_IP`
  - اجرای سرویس و توقف آن
  - مشاهده وضعیت و لاگ‌ها

---

## GUI

در این ریپازیتوری یک پنل دسکتاپ در `gui.py` وجود دارد.

### GUI چه کارهایی انجام می‌دهد

- `config.json` را بارگذاری و ذخیره می‌کند
- امکان ویرایش مستقیم این کلیدها را می‌دهد:
  - `LISTEN_HOST`
  - `LISTEN_PORT`
  - `CONNECT_IP`
  - `CONNECT_PORT`
  - `FAKE_SNI`
  - `DEBUG`
  - `HANDLE_LIMIT`
  - `ACCEPT_BACKLOG`
  - `CONNECT_TIMEOUT`
  - `HANDSHAKE_TIMEOUT`
  - `RESOURCE_PRESSURE_BACKOFF`
  - `FAKE_SEND_WORKERS`
  - `NARROW_WINDIVERT_FILTER`
- یک اسکنر دامین ارائه می‌دهد که:
  - دامین‌ها را خط‌به‌خط می‌گیرد
  - IPv4 را resolve می‌کند
  - ping/latency را اندازه می‌گیرد
  - نتیجه‌ها را در جدول نشان می‌دهد
  - بهترین گزینه را خودکار انتخاب می‌کند
  - امکان اعمال دستی نتیجه‌ی انتخاب‌شده را می‌دهد
- `FAKE_SNI` و `CONNECT_IP` را بر اساس نتیجه‌ی انتخاب‌شده به‌روزرسانی می‌کند
- کنترل‌های runtime را فراهم می‌کند:
  - `RUN`
  - `STOP`
  - `Clear log`
- اطلاعات اجرای برنامه را نمایش می‌دهد:
  - وضعیت سرویس
  - آدرس proxy
  - target فعلی
  - منبع اجرا
  - لاگ زنده‌ی سرویس

### استفاده از GUI

اجرای GUI:

```bash
python gui.py
```

اگر `bypass.exe` کنار GUI وجود داشته باشد، می‌تواند به‌عنوان هدف اجرا استفاده شود. در غیر این صورت، بسته به setup محلی، GUI می‌تواند سورس پایتون را مستقیم اجرا کند.

---

## فایل‌های اصلی

- `main.py` — نقطه شروع سرویس و منطق اصلی runtime / relay
- `fake_tcp.py` — منطق رهگیری packet و تزریق fake TCP/TLS
- `gui.py` — رابط گرافیکی برای تنظیمات، اسکن، و کنترل runtime
- `config.json` — فایل تنظیمات runtime

---

## تنظیمات پیشنهادی

```json
{
  "LISTEN_HOST": "127.0.0.1",
  "LISTEN_PORT": 400,
  "CONNECT_IP": "104.16.79.73",
  "CONNECT_PORT": 443,
  "FAKE_SNI": "static.cloudflareinsights.com",
  "DEBUG": false,
  "HANDLE_LIMIT": 64,
  "ACCEPT_BACKLOG": 128,
  "CONNECT_TIMEOUT": 5,
  "HANDSHAKE_TIMEOUT": 2,
  "RESOURCE_PRESSURE_BACKOFF": 0.5,
  "FAKE_SEND_WORKERS": 2,
  "NARROW_WINDIVERT_FILTER": true
}
```

اگر parse شدن فیلتر یا startup مشکل داشت:

```json
{
  "NARROW_WINDIVERT_FILTER": false
}
```

---

## اجرا از روی سورس

```bash
pip install -r requirements.txt
python main.py
python gui.py
```

> در ویندوز، برای اجرای مبتنی بر WinDivert معمولاً دسترسی administrator لازم است.

---

## ساخت فایل اجرایی

```bash
python -m PyInstaller --clean --noconfirm --onefile --console --uac-admin --name bypass --paths . --collect-binaries pydivert --hidden-import utils.network_tools --hidden-import utils.packet_templates main.py
python -m PyInstaller --clean --noconfirm --onefile --windowed --uac-admin --name gui --paths . gui.py
```

فایل `config.json` را کنار فایل‌های اجرایی نگه دار، مگر اینکه منطق مسیرهای runtime را تغییر داده باشی.

---

## اعتبار

- **نویسنده اصلی:** `patterniha`
- **منبع اصلی:** `https://github.com/patterniha/`
- **نگهداری فعلی:** این فورک
