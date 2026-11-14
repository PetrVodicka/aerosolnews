# Atmosféra & aerosoly – přehled článků

Skript `atmo_news.py` každý den automaticky projde populárně-vědecké weby a vědecké časopisy
(RSS + Crossref), vybere články o aerosolech, kvalitě ovzduší, atmosféře, prachu, klimatu
a atmosférách jiných planet a zveřejní je jako webovou stránku. V mobilu ji otevřete jako
aplikaci z ikony na ploše.

- **Široký výběr (7 dní):** `https://VAS-UCET.github.io/NAZEV-REPOZITARE/`
- **Užší výběr (30 dní):** `https://VAS-UCET.github.io/NAZEV-REPOZITARE/uzky.html`

---

## Nastavení (jednou, asi 15 minut)

### 1. Účet na GitHubu
Zaregistrujte se zdarma na <https://github.com/signup> (pokud účet ještě nemáte).

### 2. Nový repozitář
1. Vpravo nahoře klikněte na **+** → **New repository**.
2. Název např. `aerosoly`, zvolte **Public**.
   (GitHub Pages je na bezplatném účtu jen pro veřejné repozitáře. Na stránce jsou jen
   odkazy na veřejné články, nic citlivého.)
3. Klikněte na **Create repository**.

### 3. Nahrání souborů
1. V novém repozitáři klikněte na odkaz **uploading an existing file**.
2. Přetáhněte do okna **celý obsah** rozbalené složky: `atmo_news.py`, `README.md`,
   oba `.bat` soubory a složky `docs` a `.github`.
3. Dole klikněte na **Commit changes**.

> **Zkontrolujte, že se nahrála složka `.github`** (ve výpisu repozitáře musí být vidět).
> Ve Windows může být skrytá. Pokud chybí: **Add file → Create new file**, do názvu napište
> `.github/workflows/aktualizace.yml`, vložte obsah stejnojmenného souboru a uložte.

### 4. Zapnutí webové stránky (GitHub Pages)
1. **Settings** → v levém menu **Pages**.
2. *Source:* **Deploy from a branch**, *Branch:* **main**, složka **/docs** → **Save**.

### 5. Povolení zápisu pro automat
**Settings → Actions → General** → dole *Workflow permissions* → **Read and write permissions** → **Save**.

### 6. První spuštění
1. Záložka **Actions** → vlevo **Aktualizace přehledu článků** → **Run workflow** → **Run workflow**.
2. Běh trvá několik minut (zelená fajfka = hotovo).
3. Zhruba minutu poté je stránka dostupná na adrese uvedené nahoře
   (přesnou adresu najdete i v **Settings → Pages**).

Od teď se přehled aktualizuje **každý den ráno** (kolem 5–6 h českého času).

### 7. Ikona na ploše mobilu (Android)
1. Otevřete adresu stránky v **Chrome**.
2. Menu **⋮** → **Přidat na plochu** (případně **Instalovat aplikaci**).
3. Na ploše přibude ikona „Aerosoly“, stránka se otevírá na celou obrazovku jako aplikace.

---

## Volitelné

- **E-mail pro Crossref:** *Settings → Secrets and variables → Actions → New repository secret*,
  název `CROSSREF_MAILTO`, hodnota = váš e-mail. Crossref pak dotazy obsluhuje přednostně.
  E-mail se nikde nezveřejní.
- **Jiný čas aktualizace:** v souboru `.github/workflows/aktualizace.yml` upravte řádek `cron`
  (čas je v UTC).
- **Zdroje a klíčová slova:** upravte seznamy `FEEDS`, `KEYWORDS`, `CROSSREF_JOURNALS`
  přímo v `atmo_news.py` (na GitHubu ikonou tužky). Změna se projeví při dalším běhu.

## Poznámky

- Štítek **„nové“** označuje články, které přibyly od předchozí aktualizace.
- Soubory `archiv_clanku.json` a `videne_clanky*.json` si automat ukládá sám, nemažte je.
- Některé weby mohou blokovat stahování ze serverů GitHubu. Přehled je v reportu dole
  pod **Stav zdrojů**.
- Skript lze dál spouštět i na počítači (`spustit.bat`, `spustit_uzky.bat`).
