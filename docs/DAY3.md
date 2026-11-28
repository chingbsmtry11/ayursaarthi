# Day 3: Public link, always-on service, polish, fallback video

Goal by tonight: **https://aayu.svasthaayu.in** opens the AyurSaarthi demo for anyone,
with HTTPS, and keeps running after reboots, crashes and closed SSH windows.

## Step 1: Point the domain at the server (10 min + waiting)

Add one DNS record where **svasthaayu.in** is managed:

| Field | Value |
|---|---|
| Type | **A** |
| Name / Host | **aayu** |
| Points to / Value | **189.72.150.9** |
| TTL | 300 (or the lowest offered) |

**If the domain is on Hostinger:** hPanel → **Domains** → svasthaayu.in → **DNS / Nameservers**
→ **DNS records** → Type A, Name `aayu`, Points to `189.72.150.9`, TTL 300 → **Add record**.

**If it is somewhere else** (GoDaddy, Namecheap, Cloudflare, BigRock…): open that site's
**DNS management** for svasthaayu.in and add the same A record.
On **Cloudflare**, set the cloud to **grey ("DNS only")**, or HTTPS setup fails.

Don't know where it is managed? On your PC (PowerShell):
```powershell
nslookup -type=ns svasthaayu.in
```
The answer's nameservers tell you (e.g. `ns1.dns-parking.com` = Hostinger).

**Check it worked** (PowerShell on your PC, after 5-15 minutes):
```powershell
nslookup aayu.svasthaayu.in
```
It must show `Address: 189.72.150.9`. Until it does, Step 3 stops safely and tells you so.

## Step 2: Copy the Day 3 code (5 min)
PowerShell tab (your PC):
```powershell
scp "$HOME\Downloads\ayursaarthi_day3.zip" root@189.72.150.9:/root/
```
Server tab:
```bash
cd /root && unzip -o ayursaarthi_day3.zip && cd ayursaarthi
source .venv/bin/activate
MOCK_LLM=1 python -m scripts.day2_test | tail -3     # expect TOTAL 48/50
```

## Step 3: Deploy (5 min)
Server tab:
```bash
make deploy
```
It checks DNS, stops the old background copy, installs two services (web demo + API) that
start on boot and restart on crash, installs **Caddy**, which gets the HTTPS certificate by
itself, and tests everything. The last lines should show:
```
UI local:   200
API local:  {"status":"ok","verses":43,...}
Public:     200
Public API: {"status":"ok",...}
```
Open **https://aayu.svasthaayu.in** on your phone (mobile data, not Wi-Fi) to be sure it is
public. You no longer need the `ssh -L` tunnel.

Useful later:
```bash
make status     # all four should say "active (running)"
make logs       # last lines of the web demo
systemctl restart ayursaarthi-ui    # after changing code or data
```

## Step 4: Check the polish (5 min)
On https://aayu.svasthaayu.in:
- `गिलोय के गुण क्या हैं` -> plain Hindi answer, and only **BPN.Guduchyadi.8** under sources
- `I am pregnant, can I take Haritaki?` -> the ⛔ warning is now the **first** thing shown
- Footer links: **Source code** (GitHub) and **API** (`/api/docs`)

## Step 5: Save to GitHub
```bash
git add . && git commit -m "Day 3: public HTTPS at aayu.svasthaayu.in, services, polish" && git push
```

## Step 6: Record a fallback video (15 min)
In case the internet or server fails on 16 Dec. Windows 11: **Snipping Tool → Record**
(or Win+Shift+R), select the browser window, record about 2-3 minutes:
1. Home page and the one-line idea: "every answer cites a verse, or says it has none"
2. `What is the virya of Amalaki?` -> open the Sanskrit verse
3. `गिलोय के गुण क्या हैं` (Hindi) and `neem ke fayde` (Hinglish)
4. Safety: `I am pregnant, can I take Haritaki?`, `How much Ashwagandha should I take?`,
   `I have chest pain spreading to my left arm`, `Quote Charaka Samhita Sutrasthana 99.1`
5. Prescription tab and Department tab
6. GitHub page, and `/api/docs`
Save it to Google Drive and keep a copy on your laptop and phone.

## If something goes wrong
- `STOP: the DNS A record ... does not point` -> wait longer; check with `nslookup` (Step 1)
- `Public: 000` or a certificate error -> `journalctl -u caddy -n 30 --no-pager`; ports 80/443
  must be open: `ufw status` should list 80 and 443 (setup_vps.sh opened them). In the Hostinger
  VPS panel, check that no extra firewall blocks 80/443.
- Page says 502 -> the app is still loading (about 30 s after a restart), or check `make logs`
- Anything else -> screenshot and send it.
