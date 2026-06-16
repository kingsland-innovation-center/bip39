# AGENTS.md

## Cursor Cloud specific instructions

This repo is the **BIP39 tool** — a fully client-side, static web app (HTML + JS).
There is no server, no build step, and no transpilation needed to run it.

### Running the app
The app is just static files in `src/`. Serve them and open `index.html`:

```
cd src && python3 -m http.server 8000
```

Then open `http://localhost:8000/index.html`. Core flow: type a BIP39 mnemonic into
the "BIP39 Mnemonic" field and the "Derived Addresses" table populates with
addresses / public keys / private keys.

`compile.py` (run from repo root: `python3 compile.py`) inlines all `src/*` scripts
and styles into a single `bip39-standalone.html` (gitignored). Edit files in `src/*`,
never `bip39-standalone.html` directly.

### Lint
There is no linter configured for this project.

### Tests
Tests live in `tests/` and use **selenium-webdriver (headless Chrome)** + **jasmine**.
See `readme.md` for the original instructions. Run from `tests/`:

```
cd tests
./node_modules/.bin/jasmine spec/tests.js                       # full suite (slow)
./node_modules/.bin/jasmine spec/tests.js --filter="litecoin"   # run a subset
```

`BROWSER` defaults to `chrome`. The `firefox` path is broken (see comment in
`tests/spec/tests.js`).

### Non-obvious gotchas
- **Jasmine must be v3.x.** These 2020-era tests use the legacy Selenium
  control-flow / `done`-callback style, which is incompatible with modern jasmine 5
  (specs never complete and the runner exits prematurely with code 4 and no spec
  output). The update script pins `jasmine@^3.6.0`. Do **not** `npm install -g jasmine`
  (that installs v5). The default Selenium promise manager is fine — no need to set
  `SELENIUM_PROMISE_MANAGER`.
- **chromedriver must match the installed `google-chrome` major version.** Chrome is
  pre-installed in the image but chromedriver is not part of the base image. The
  update script installs a matching `chromedriver` into `/usr/local/bin`. If tests
  fail with a "session not created: version mismatch" error after a Chrome upgrade,
  re-run the update script (it detects the Chrome major version and downloads the
  matching driver from Chrome for Testing).
- The full suite is slow: each spec spins up a fresh headless Chrome, and the BIP38
  tests `sleep` ~15s each. Prefer `--filter=...` while iterating.
